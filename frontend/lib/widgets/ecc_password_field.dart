import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class EccPasswordField extends StatefulWidget {
  final TextEditingController controller;
  final bool enabled;
  final String label;
  final bool allowWildcards;

  const EccPasswordField({
    super.key,
    required this.controller,
    this.enabled = true,
    this.label = 'Password',
    this.allowWildcards = true,
  });

  @override
  State<EccPasswordField> createState() => _EccPasswordFieldState();
}

class _EccPasswordFieldState extends State<EccPasswordField> {
  bool _obscureText = true;

  void _insertWildcard() {
    if (!widget.allowWildcards) return;

    final text = widget.controller.text;
    final selection = widget.controller.selection;

    // Check budget (max 4 erasures as per implementation plan)
    final erasures = text.split('').where((c) => c == '*').length;
    if (erasures >= 4) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Maximum 4 wildcards allowed for ECC correction.'),
          backgroundColor: Color(0xFFEF4444),
        ),
      );
      return;
    }

    final newText = text.replaceRange(
      selection.start != -1 ? selection.start : text.length,
      selection.end != -1 ? selection.end : text.length,
      '*',
    );

    widget.controller.value = widget.controller.value.copyWith(
      text: newText,
      selection: TextSelection.collapsed(
        offset: (selection.start != -1 ? selection.start : text.length) + 1,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: widget.controller,
      enabled: widget.enabled,
      obscureText: _obscureText,
      style: GoogleFonts.inter(
        color: Colors.white,
        letterSpacing: _obscureText ? 2.0 : 0.5,
      ),
      decoration: InputDecoration(
        labelText: widget.label,
        prefixIcon: const Icon(Icons.lock_outline_rounded, color: Color(0xFF6366F1)),
        suffixIcon: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (widget.allowWildcards)
              IconButton(
                tooltip: 'Insert wildcard (*)',
                icon: const Icon(Icons.star_rounded, color: Color(0xFF818CF8)),
                onPressed: widget.enabled ? _insertWildcard : null,
              ),
            IconButton(
              icon: Icon(
                _obscureText ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                color: const Color(0xFF64748B),
              ),
              onPressed: () => setState(() => _obscureText = !_obscureText),
            ),
            const SizedBox(width: 8),
          ],
        ),
      ),
      validator: (v) {
        if (v == null || v.isEmpty) return '${widget.label} required';
        if (v.length < 6) return 'Minimum 6 characters';
        return null;
      },
    );
  }
}
