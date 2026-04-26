import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'features/auth/login_screen.dart';
import 'features/vault/vault_screen.dart';
import 'core/secure_storage.dart';

class SecureCorrectApp extends StatelessWidget {
  const SecureCorrectApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SecureCorrect',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(),
      initialRoute: '/login',
      routes: {
        '/login': (_) => const LoginScreen(),
        '/vault': (_) => const VaultScreen(),
      },
    );
  }

  ThemeData _buildTheme() {
    const bg = Color(0xFF0A0E1A);
    const surface = Color(0xFF111827);
    const card = Color(0xFF1A2235);
    const accent = Color(0xFF6366F1);      // indigo
    const accentAlt = Color(0xFF8B5CF6);   // violet
    const onBg = Color(0xFFE2E8F0);
    const subtle = Color(0xFF64748B);

    final base = ThemeData.dark();
    return base.copyWith(
      scaffoldBackgroundColor: bg,
      colorScheme: const ColorScheme.dark(
        primary: accent,
        secondary: accentAlt,
        surface: surface,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
        onSurface: onBg,
      ),
      cardColor: card,
      textTheme: GoogleFonts.interTextTheme(base.textTheme).apply(
        bodyColor: onBg,
        displayColor: onBg,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: card,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFF2D3748)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: Color(0xFF2D3748)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: accent, width: 2),
        ),
        hintStyle: const TextStyle(color: subtle),
        labelStyle: const TextStyle(color: subtle),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          padding: const EdgeInsets.symmetric(vertical: 18),
          textStyle: GoogleFonts.inter(fontWeight: FontWeight.w600, fontSize: 16),
          elevation: 0,
        ),
      ),
      snackBarTheme: const SnackBarThemeData(
        backgroundColor: card,
        contentTextStyle: TextStyle(color: onBg),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
        ),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
