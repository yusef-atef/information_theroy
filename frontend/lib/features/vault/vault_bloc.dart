import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import '../../core/api_client.dart';
import '../../core/models/file_item.dart';

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
  VaultOperationSuccess({required this.message, required this.files});
  @override
  List<Object?> get props => [message, files];
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

    emit(VaultUploading(0));
    try {
      await _dio.uploadFile(picked.path!, picked.name);
      emit(VaultUploading(1));
      // Reload list
      final raw = await _dio.listFiles();
      _cachedFiles = raw.map((e) => FileItem.fromJson(e as Map<String, dynamic>)).toList();
      emit(VaultOperationSuccess(
        message: '${picked.name} encrypted and uploaded',
        files: _cachedFiles,
      ));
    } on DioException catch (e) {
      emit(VaultError(_parseError(e)));
    }
  }

  Future<void> _onDownload(DownloadFileRequested event, Emitter<VaultState> emit) async {
    // Avoid full-screen loading for downloads to prevent UI disruption
    // Instead, we can just use a snackbar or a small indicator if needed, 
    // but for now let's just ensure we return to Loaded state regardless.
    try {
      final bytes = await _dio.downloadFile(event.file.id);
      
      // Save to a more accessible location if possible, or just open from cache
      final dir = await getTemporaryDirectory(); // Use temp for opening
      final path = '${dir.path}/${event.file.filename}';
      final file = File(path);
      await file.writeAsBytes(bytes);
      
      await OpenFilex.open(path);
      
      emit(VaultOperationSuccess(
        message: 'File downloaded: ${event.file.filename}',
        files: _cachedFiles,
      ));
    } on DioException catch (e) {
      emit(VaultError(_parseError(e)));
    } catch (e) {
      emit(VaultError('Failed to save or open file: $e'));
    } finally {
      // Always ensure we are back in a stable state
      if (state is! VaultLoaded && state is! VaultOperationSuccess) {
        emit(VaultLoaded(_cachedFiles));
      }
    }
  }

  Future<void> _onDelete(DeleteFileRequested event, Emitter<VaultState> emit) async {
    try {
      await _dio.deleteFile(event.fileId);
      _cachedFiles.removeWhere((f) => f.id == event.fileId);
      emit(VaultOperationSuccess(
        message: 'File deleted successfully',
        files: List.from(_cachedFiles),
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
