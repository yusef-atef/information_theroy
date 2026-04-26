import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';
import '../../core/secure_storage.dart';
import '../../core/models/user.dart';
import '../../core/crypto_engine.dart';
import '../../core/biometric_service.dart';
import '../../core/ecc/ecc_auth.dart';
import 'package:convert/convert.dart';

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

abstract class AuthEvent extends Equatable {
  @override
  List<Object?> get props => [];
}

class LoginSubmitted extends AuthEvent {
  final String username;
  final String password; // may contain '*' wildcards

  LoginSubmitted({required this.username, required this.password});

  @override
  List<Object?> get props => [username, password];
}

class RegisterSubmitted extends AuthEvent {
  final String username;
  final String email;
  final String password;

  RegisterSubmitted({
    required this.username,
    required this.email,
    required this.password,
  });

  @override
  List<Object?> get props => [username, email, password];
}

class LogoutRequested extends AuthEvent {}

class AccountDeletionRequested extends AuthEvent {}

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------

abstract class AuthState extends Equatable {
  @override
  List<Object?> get props => [];
}

class AuthInitial extends AuthState {}

class AuthLoading extends AuthState {}

class AuthSuccess extends AuthState {
  final UserModel user;
  final int correctionsApplied;
  final int erasuresFilled;

  AuthSuccess({
    required this.user,
    this.correctionsApplied = 0,
    this.erasuresFilled = 0,
  });

  bool get hadCorrections => correctionsApplied > 0 || erasuresFilled > 0;

  @override
  List<Object?> get props => [user, correctionsApplied, erasuresFilled];
}

class AuthFailure extends AuthState {
  final String message;
  AuthFailure(this.message);

  @override
  List<Object?> get props => [message];
}

class RegisterSuccess extends AuthState {
  final String username;
  RegisterSuccess(this.username);

  @override
  List<Object?> get props => [username];
}

// ---------------------------------------------------------------------------
// BLoC
// ---------------------------------------------------------------------------

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  AuthBloc() : super(AuthInitial()) {
    on<LoginSubmitted>(_onLogin);
    on<RegisterSubmitted>(_onRegister);
    on<LogoutRequested>(_onLogout);
    on<AccountDeletionRequested>(_onDeleteAccount);
  }

  final _dio = ApiClient.instance.dio;

  Future<void> _onLogin(LoginSubmitted event, Emitter<AuthState> emit) async {
    emit(AuthLoading());
    try {
      // 1. Step 1: Fetch ECC parity symbols and mapping seed
      final step1Data = await _dio.loginStep1(username: event.username);
      final codewordHex = step1Data['codeword_hex'] as String;
      final seedHex = step1Data['seed_hex'] as String;

      final codeword = hex.decode(codewordHex);
      final seed = hex.decode(seedHex);

      // 2. Perform Local ECC Correction
      final correction = EccAuth.verifyAndCorrect(
        event.password,
        codeword,
        seed,
      );

      if (!correction.success) {
        emit(AuthFailure('Invalid credentials or too many typos to correct.'));
        return;
      }

      final correctedPassword = correction.correctedPassword!;

      // 3. Derive Authentication Hash (Proof)
      // Use username as salt for key derivation
      final authKey = await CryptoEngine.deriveKey(correctedPassword, event.username);
      final authKeyBytes = await authKey.extractBytes();
      final authHash = hex.encode(authKeyBytes);

      // 4. Step 2: Submit Proof
      final tokenData = await _dio.loginStep2(
        username: event.username,
        authHash: authHash,
      );

      await SecureStorage.saveTokens(
        accessToken: tokenData['access_token'] as String,
        refreshToken: tokenData['refresh_token'] as String,
      );
      await SecureStorage.saveUsername(event.username);
      await SecureStorage.savePassword(correctedPassword);

      final userData = await _dio.getMe();
      final user = UserModel.fromJson(userData);

      emit(AuthSuccess(
        user: user,
        correctionsApplied: correction.errorsCorrected,
        erasuresFilled: correction.erasuresFilled,
      ));
    } on DioException catch (e) {
      emit(AuthFailure(_parseError(e)));
    } catch (e) {
      emit(AuthFailure('Login error: $e'));
    }
  }

  Future<void> _onRegister(RegisterSubmitted event, Emitter<AuthState> emit) async {
    emit(AuthLoading());
    try {
      // 1. Generate ECC Codeword and Seed locally
      final bundle = EccAuth.registerPassword(event.password);
      
      // 2. Derive Authentication Hash
      final authKey = await CryptoEngine.deriveKey(event.password, event.username);
      final authKeyBytes = await authKey.extractBytes();
      final authHash = hex.encode(authKeyBytes);

      // 3. Submit to server
      await _dio.register(
        username: event.username,
        email: event.email,
        codewordHex: hex.encode(bundle.codeword),
        seedHex: hex.encode(bundle.seed),
        authHash: authHash,
      );
      
      emit(RegisterSuccess(event.username));
    } on DioException catch (e) {
      emit(AuthFailure(_parseError(e)));
    } catch (e) {
      emit(AuthFailure('Registration error: $e'));
    }
  }

  Future<void> _onLogout(LogoutRequested event, Emitter<AuthState> emit) async {
    await SecureStorage.clearAll();
    emit(AuthInitial());
  }

  Future<void> _onDeleteAccount(AccountDeletionRequested event, Emitter<AuthState> emit) async {
    // Authenticate with Biometrics before account deletion
    final authenticated = await BiometricService.authenticate(
      reason: 'Confirm your identity to PERMANENTLY delete your account and all files',
    );
    if (!authenticated) {
      emit(AuthFailure('Biometric authentication failed or was cancelled'));
      return;
    }

    emit(AuthLoading());
    try {
      await _dio.deleteAccount();
      await SecureStorage.clearAll();
      emit(AuthInitial());
    } on DioException catch (e) {
      emit(AuthFailure(_parseError(e)));
    } catch (e) {
      emit(AuthFailure('Failed to delete account: $e'));
    }
  }

  String _parseError(DioException e) {
    final data = e.response?.data;
    if (data is Map && data['detail'] != null) return data['detail'].toString();
    return e.message ?? 'An unknown error occurred';
  }
}
