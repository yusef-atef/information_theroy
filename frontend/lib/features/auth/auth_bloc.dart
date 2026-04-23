import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import '../../core/api_client.dart';
import '../../core/secure_storage.dart';
import '../../core/models/user.dart';

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
  }

  final _dio = ApiClient.instance.dio;

  Future<void> _onLogin(LoginSubmitted event, Emitter<AuthState> emit) async {
    emit(AuthLoading());
    try {
      final tokenData = await _dio.login(
        username: event.username,
        password: event.password,
      );

      await SecureStorage.saveTokens(
        accessToken: tokenData['access_token'] as String,
        refreshToken: tokenData['refresh_token'] as String,
      );
      await SecureStorage.saveUsername(event.username);

      final userData = await _dio.getMe();
      final user = UserModel.fromJson(userData);

      emit(AuthSuccess(
        user: user,
        correctionsApplied: tokenData['corrections_applied'] as int? ?? 0,
        erasuresFilled: tokenData['erasures_filled'] as int? ?? 0,
      ));
    } on DioException catch (e) {
      final msg = _parseError(e);
      emit(AuthFailure(msg));
    }
  }

  Future<void> _onRegister(RegisterSubmitted event, Emitter<AuthState> emit) async {
    emit(AuthLoading());
    try {
      await _dio.register(
        username: event.username,
        email: event.email,
        password: event.password,
      );
      emit(RegisterSuccess(event.username));
    } on DioException catch (e) {
      emit(AuthFailure(_parseError(e)));
    }
  }

  Future<void> _onLogout(LogoutRequested event, Emitter<AuthState> emit) async {
    await SecureStorage.clearAll();
    emit(AuthInitial());
  }

  String _parseError(DioException e) {
    final data = e.response?.data;
    if (data is Map && data['detail'] != null) return data['detail'].toString();
    return e.message ?? 'An unknown error occurred';
  }
}
