import 'package:equatable/equatable.dart';

class FileItem extends Equatable {
  final String id;
  final String filename;
  final String mimeType;
  final int sizeBytes;
  final String? googleFileId;
  final DateTime createdAt;

  const FileItem({
    required this.id,
    required this.filename,
    required this.mimeType,
    required this.sizeBytes,
    this.googleFileId,
    required this.createdAt,
  });

  factory FileItem.fromJson(Map<String, dynamic> json) => FileItem(
        id: json['id'] as String,
        filename: json['filename'] as String,
        mimeType: json['mime_type'] as String,
        sizeBytes: json['size_bytes'] as int,
        googleFileId: json['google_file_id'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  String get formattedSize {
    if (sizeBytes < 1024) return '$sizeBytes B';
    if (sizeBytes < 1024 * 1024) return '${(sizeBytes / 1024).toStringAsFixed(1)} KB';
    return '${(sizeBytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }

  String get extension {
    final parts = filename.split('.');
    return parts.length > 1 ? parts.last.toLowerCase() : '';
  }

  @override
  List<Object?> get props => [id, filename, sizeBytes, createdAt];
}
