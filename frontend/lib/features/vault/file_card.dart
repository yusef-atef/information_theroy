import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../../core/models/file_item.dart';

class FileCard extends StatefulWidget {
  final FileItem file;
  final VoidCallback onDownload;
  final VoidCallback onDelete;

  const FileCard({
    super.key,
    required this.file,
    required this.onDownload,
    required this.onDelete,
  });

  @override
  State<FileCard> createState() => _FileCardState();
}

class _FileCardState extends State<FileCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _hoverCtrl;
  late final Animation<double> _scaleAnim;

  @override
  void initState() {
    super.initState();
    _hoverCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 150));
    _scaleAnim = Tween(begin: 1.0, end: 0.97)
        .animate(CurvedAnimation(parent: _hoverCtrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _hoverCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => _hoverCtrl.forward(),
      onTapUp: (_) => _hoverCtrl.reverse(),
      onTapCancel: () => _hoverCtrl.reverse(),
      child: ScaleTransition(
        scale: _scaleAnim,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            color: const Color(0xFF1A2235),
            border: Border.all(color: const Color(0xFF1E293B), width: 1.2),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.25),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                _buildFileIcon(),
                const SizedBox(width: 14),
                Expanded(child: _buildFileInfo()),
                _buildActions(),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // -------------------------------------------------------------------------
  // File type icon
  // -------------------------------------------------------------------------
  Widget _buildFileIcon() {
    final ext = widget.file.extension;
    final (icon, color) = _iconForExt(ext);
    return Container(
      width: 52,
      height: 52,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        color: color.withOpacity(0.12),
        border: Border.all(color: color.withOpacity(0.3), width: 1),
      ),
      child: Stack(
        alignment: Alignment.center,
        children: [
          Icon(icon, color: color, size: 26),
          Positioned(
            bottom: 4,
            right: 4,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4),
                color: color.withOpacity(0.9),
              ),
              child: Text(
                ext.isEmpty ? '?' : ext.toUpperCase(),
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 7,
                    fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ],
      ),
    );
  }

  (IconData, Color) _iconForExt(String ext) {
    return switch (ext) {
      'pdf' => (Icons.picture_as_pdf_rounded, const Color(0xFFEF4444)),
      'jpg' || 'jpeg' || 'png' || 'gif' || 'webp' => (
          Icons.image_rounded,
          const Color(0xFF10B981)
        ),
      'mp4' || 'mov' || 'avi' => (
          Icons.videocam_rounded,
          const Color(0xFF3B82F6)
        ),
      'mp3' || 'wav' || 'flac' => (
          Icons.music_note_rounded,
          const Color(0xFFF59E0B)
        ),
      'zip' || 'rar' || 'tar' || 'gz' => (
          Icons.folder_zip_rounded,
          const Color(0xFF8B5CF6)
        ),
      'doc' || 'docx' => (Icons.description_rounded, const Color(0xFF2563EB)),
      'xls' || 'xlsx' => (
          Icons.table_chart_rounded,
          const Color(0xFF059669)
        ),
      _ => (Icons.insert_drive_file_rounded, const Color(0xFF64748B)),
    };
  }

  // -------------------------------------------------------------------------
  // File info
  // -------------------------------------------------------------------------
  Widget _buildFileInfo() {
    final date = DateFormat('MMM d, yyyy').format(widget.file.createdAt.toLocal());
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          widget.file.filename,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: GoogleFonts.inter(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            _pill(widget.file.formattedSize, const Color(0xFF334155),
                const Color(0xFF94A3B8)),
            const SizedBox(width: 6),
            _pill('🔒 Encrypted', const Color(0xFF1E3A5F),
                const Color(0xFF60A5FA)),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          date,
          style: GoogleFonts.inter(
              fontSize: 11, color: const Color(0xFF475569)),
        ),
      ],
    );
  }

  Widget _pill(String text, Color bg, Color fg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(6),
        color: bg,
      ),
      child: Text(text,
          style: GoogleFonts.inter(fontSize: 11, color: fg)),
    );
  }

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------
  Widget _buildActions() {
    return Column(
      children: [
        _actionBtn(
          icon: Icons.download_rounded,
          color: const Color(0xFF6366F1),
          tooltip: 'Download & decrypt',
          onTap: widget.onDownload,
        ),
        const SizedBox(height: 8),
        _actionBtn(
          icon: Icons.delete_outline_rounded,
          color: const Color(0xFFEF4444),
          tooltip: 'Delete',
          onTap: widget.onDelete,
        ),
      ],
    );
  }

  Widget _actionBtn({
    required IconData icon,
    required Color color,
    required String tooltip,
    required VoidCallback onTap,
  }) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            color: color.withOpacity(0.12),
          ),
          child: Icon(icon, color: color, size: 18),
        ),
      ),
    );
  }
}
