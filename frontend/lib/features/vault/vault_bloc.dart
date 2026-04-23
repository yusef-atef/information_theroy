import 'package:equatable/equatable.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:convert/convert.dart';
import 'package:cryptography/cryptography.dart';
import '../../core/api_client.dart';
import '../../core/models/file_item.dart';
import '../../core/crypto_engine.dart';
import '../../core/biometric_service.dart';
import '../../core/secure_storage.dart';

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

abstract class VaultEvent extends Equatable {
  @override
  List<Object?> get props => [];
}

class LoadFiles extends VaultEvent {}

class UploadFileRequested extends VaultEvent {}

class DownloadFileRequested extends VaultEvent {
  final FileItem file;
  DownloadFileRequested(this.file);
  @override
  List<Object?> get props => [file];
}

class DeleteFileRequested extends VaultEvent {
  final String fileId;
  DeleteFileRequested(this.fileId);
  @override
  List<Object?> get props => [fileId];
}

// ---------------------------------------------------------------------------
// States
// ---------------------------------------------------------------------------

abstract class VaultState extends Equatable {
  @override
  List<Object?> get props => [];
}

class VaultInitial extends VaultState {}

class VaultLoading extends VaultState {}

class VaultLoaded extends VaultState {
  final List<FileItem> files;
  VaultLoaded(this.files);
  @override
  List<Object?> get props => [files];
}

class VaultOperationSuccess extends VaultState {
  final String message;
  final List<FileItem> files;
  VaultOperationSuccess(this.message, this.files);
  @override
  List<Object?> get props => [message, files];
}

class VaultPreviewReady extends VaultState {
  final Uint8List bytes;
  final String filename;
  VaultPreviewReady(this.bytes, this.filename);
  @override
  List<Object?> get props => [bytes, filename];
}

class VaultError extends VaultState {
  final String message;
  VaultError(this.message);
  @override
  List<Object?> get props => [message];
}

class VaultUploading extends VaultState {
  final double progress;
  VaultUploading(this.progress);
  @override
  List<Object?> get props => [progress];
}

// ---------------------------------------------------------------------------
// BLoC
// ---------------------------------------------------------------------------

class VaultBloc extends Bloc<VaultEvent, VaultState> {
  VaultBloc() : super(VaultInitial()) {
    on<LoadFiles>(_onLoad);
    on<UploadFileRequested>(_onUpload);
    on<DownloadFileRequested>(_onDownload);
    on<DeleteFileRequested>(_onDelete);
  }

  final _dio = ApiClient.instance.dio;
  List<FileItem> _cachedFiles = [];

  Future<void> _onLoad(LoadFiles event, Emitter<VaultState> emit) async {
    emit(VaultLoading());
    try {
      final raw = await _dio.listFiles();
      _cachedFiles = raw.map((e) => FileItem.fromJson(e as Map<String, dynamic>)).toList();
      emit(VaultLoaded(_cachedFiles));
    } on DioException catch (e) {
      emit(VaultError(_parseError(e)));
    }
  }

  Future<void> _onUpload(UploadFileRequested event, Emitter<VaultState> emit) async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: false);
    if (result == null || result.files.isEmpty) return;

    final picked = result.files.first;
    if (picked.path == null) return;

    // 1. Authenticate with Biometrics
    final authenticated = await BiometricService.authenticate(
      reason: 'Confirm your identity to encrypt and upload ${picked.name}',
    );
    if (!authenticated) {
      emit(VaultError('Biometric authentication failed or was cancelled'));
      emit(VaultLoaded(_cachedFiles));
      return;
    }

    emit(VaultUploading(0));
    try {
      // 2. Prepare encryption
      final password = await SecureStorage.getPassword();
      final username = await SecureStorage.getUsername();
      if (password == null || username == null) throw Exception('Auth data missing');

      final plaintextBytes = await File(picked.path!).readAsBytes();
      final key = await CryptoEngine.deriveKey(password, username); // Use username as salt

      // 3. Encrypt data
      final secretBox = await AesGcm.with256bits().encrypt(
        plaintextBytes,
        secretKey: key,
      );

      // 4. Compute HMAC of plaintext for integrity
      final hmac = await CryptoEngine.generateHmac(plaintextBytes, password);

      // 5. Upload encrypted bytes with metadata
      // Create temporary file for upload
      final tempDir = await getTemporaryDirectory();
      final encryptedFile = File('${tempDir.path}/enc_${picked.name}');
      await encryptedFile.writeAsBytes(secretBox.cipherText);

      await _dio.uploadFile(
        filePath: encryptedFile.path,
        filename: picked.name,
        ivHex: hex.encode(secretBox.nonce),
        gcmTagHex: hex.encode(secretBox.mac.bytes),
        hmacHex: hex.encode(hmac),
        sizeBytes: plaintextBytes.length,
      );

      emit(VaultUploading(1));

      // 6. Cleanup local files (Zero-Knowledge: leave no traces)
      try {
        await File(picked.path!).delete();
        await encryptedFile.delete();
      } catch (e) {
        // Log but don't fail the operation if cleanup fails (e.g. permission issue)
        debugPrint('Cleanup error: $e');
      }
      
      // Reload list
      final raw = await _dio.listFiles();
      _cachedFiles = raw.map((e) => FileItem.fromJson(e as Map<String, dynamic>)).toList();
      
      emit(VaultOperationSuccess(
        '${picked.name} encrypted and uploaded',
        _cachedFiles,
      ));
    } on DioException catch (e) {
      emit(VaultError(_parseError(e)));
    } catch (e) {
      emit(VaultError('Upload error: $e'));
    }
  }

  Future<void> _onDownload(DownloadFileRequested event, Emitter<VaultState> emit) async {
    try {
      // 1. Download encrypted bytes + metadata from headers
      final response = await _dio.downloadFileWithMetadata(event.file.id);
      final ciphertext = response.data as List<int>;
      
      final ivHex = response.headers.value('x-iv') ?? '';
      final tagHex = response.headers.value('x-tag') ?? '';
      final hmacHex = response.headers.value('x-hmac') ?? '';

      // 2. Authenticate with Biometrics before decryption
      final authenticated = await BiometricService.authenticate(
        reason: 'Authenticate to decrypt and open ${event.file.filename}',
      );
      if (!authenticated) {
        emit(VaultError('Biometric authentication failed or was cancelled'));
        emit(VaultLoaded(_cachedFiles));
        return;
      }

      // 3. Prepare decryption
      final password = await SecureStorage.getPassword();
      final username = await SecureStorage.getUsername();
      if (password == null || username == null) throw Exception('Auth data missing');

      final key = await CryptoEngine.deriveKey(password, username);

      // 4. Decrypt
      final secretBox = SecretBox(
        Uint8List.fromList(ciphertext),
        nonce: hex.decode(ivHex),
        mac: Mac(hex.decode(tagHex)),
      );
      
      final plaintext = await AesGcm.with256bits().decrypt(
        secretBox,
        secretKey: key,
      );

      // 5. Verify integrity (optional but recommended)
      final computedHmac = await CryptoEngine.generateHmac(Uint8List.fromList(plaintext), password);
      if (hex.encode(computedHmac) != hmacHex) {
        throw Exception('Integrity check failed! Data may have been tampered with.');
      }

      // 6. Preview in-memory (Zero-Knowledge: avoid disk)
      emit(VaultPreviewReady(
        Uint8List.fromList(plaintext),
        event.file.filename,
      ));
      
      // Return to loaded state so the UI stays responsive
      emit(VaultLoaded(_cachedFiles));
    } on DioException catch (e) {
      emit(VaultError(_parseError(e)));
    } catch (e) {
      emit(VaultError('Failed to decrypt or open file: $e'));
    } finally {
      if (state is! VaultLoaded && state is! VaultOperationSuccess) {
        emit(VaultLoaded(_cachedFiles));
      }
    }
  }

  Future<void> _onDelete(DeleteFileRequested event, Emitter<VaultState> emit) async {
    // Authenticate with Biometrics before deletion
    final authenticated = await BiometricService.authenticate(
      reason: 'Confirm your identity to permanently delete this file',
    );
    if (!authenticated) {
      emit(VaultError('Biometric authentication failed or was cancelled'));
      emit(VaultLoaded(_cachedFiles));
      return;
    }

    try {
      await _dio.deleteFile(event.fileId);
      _cachedFiles.removeWhere((f) => f.id == event.fileId);
      emit(VaultOperationSuccess(
        'File deleted successfully',
        List.from(_cachedFiles),
      ));
    } on DioException catch (e) {
      emit(VaultError(_parseError(e)));
    }
  }

  String _parseError(DioException e) {
    final data = e.response?.data;
    if (data is Map && data['detail'] != null) return data['detail'].toString();
    return e.message ?? 'An unknown error occurred';
  }
}
