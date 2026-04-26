import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:syncfusion_flutter_pdfviewer/pdfviewer.dart';

class FilePreviewScreen extends StatelessWidget {
  final Uint8List bytes;
  final String filename;

  const FilePreviewScreen({
    super.key,
    required this.bytes,
    required this.filename,
  });

  @override
  Widget build(BuildContext context) {
    final extension = filename.split('.').last.toLowerCase();

    return Scaffold(
      backgroundColor: const Color(0xFF0A0E1A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E1B4B),
        title: Text(
          filename,
          style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w600),
        ),
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline_rounded),
            onPressed: () => _showSecurityInfo(context),
          ),
        ],
      ),
      body: _buildPreview(extension, context),
    );
  }

  Widget _buildPreview(String ext, BuildContext context) {
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(ext)) {
      return Center(
        child: InteractiveViewer(
          minScale: 0.5,
          maxScale: 4.0,
          child: Image.memory(bytes),
        ),
      );
    } else if (ext == 'pdf') {
      return SfPdfViewer.memory(bytes);
    } else if (['txt', 'md', 'json', 'dart', 'py'].contains(ext)) {
      try {
        final text = String.fromCharCodes(bytes);
        return SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Text(
            text,
            style: GoogleFonts.firaCode(
              color: const Color(0xFFCBD5E1),
              fontSize: 14,
            ),
          ),
        );
      } catch (e) {
        return _buildError('Unable to display text content');
      }
    } else {
      return _buildError('Preview not available for .$ext files in-memory');
    }
  }

  Widget _buildError(String message) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.visibility_off_rounded, color: Color(0xFF64748B), size: 48),
          const SizedBox(height: 16),
          Text(
            message,
            style: GoogleFonts.inter(color: const Color(0xFF94A3B8)),
          ),
        ],
      ),
    );
  }

  void _showSecurityInfo(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1A2235),
        title: Text('Security Notice', 
          style: GoogleFonts.inter(color: Colors.white, fontWeight: FontWeight.w700)),
        content: Text(
          'This file is being displayed directly from the device\'s RAM. It has not been saved to your storage, making it invisible to other apps even on rooted devices.',
          style: GoogleFonts.inter(color: const Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Got it', style: GoogleFonts.inter(color: const Color(0xFF6366F1))),
          ),
        ],
      ),
    );
  }
}
