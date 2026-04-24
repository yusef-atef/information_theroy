import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../widgets/ecc_password_field.dart';
import '../../widgets/gradient_button.dart';
import 'auth_bloc.dart';
import 'register_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  late final AnimationController _fadeCtrl;
  late final Animation<double> _fadeAnim;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 800));
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _fadeCtrl.forward();
  }

  @override
  void dispose() {
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    _fadeCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => AuthBloc(),
      child: BlocConsumer<AuthBloc, AuthState>(
        listener: _handleState,
        builder: (context, state) {
          return Scaffold(
            body: Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFF0A0E1A), Color(0xFF0D1B2A), Color(0xFF0A0E1A)],
                ),
              ),
              child: SafeArea(
                child: FadeTransition(
                  opacity: _fadeAnim,
                  child: Center(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(28),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          _buildHeader(),
                          const SizedBox(height: 40),
                          _buildCard(context, state),
                          const SizedBox(height: 24),
                          _buildRegisterLink(context),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      children: [
        Container(
          width: 72,
          height: 72,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: const LinearGradient(
              colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF6366F1).withOpacity(0.4),
                blurRadius: 24,
                spreadRadius: 4,
              ),
            ],
          ),
          child: const Icon(Icons.shield_rounded, color: Colors.white, size: 36),
        ),
        const SizedBox(height: 20),
        Text(
          'SecureCorrect',
          style: GoogleFonts.inter(
            fontSize: 30,
            fontWeight: FontWeight.w800,
            foreground: Paint()
              ..shader = const LinearGradient(
                colors: [Color(0xFF6366F1), Color(0xFF8B5CF6), Color(0xFFA78BFA)],
              ).createShader(const Rect.fromLTWH(0, 0, 240, 40)),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Your vault. Resilient to typos.',
          style: GoogleFonts.inter(
            fontSize: 14,
            color: const Color(0xFF64748B),
            letterSpacing: 0.3,
          ),
        ),
      ],
    );
  }

  Widget _buildCard(BuildContext context, AuthState state) {
    final isLoading = state is AuthLoading;
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        color: const Color(0xFF111827).withOpacity(0.9),
        border: Border.all(color: const Color(0xFF1E293B), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.4),
            blurRadius: 32,
            offset: const Offset(0, 16),
          ),
        ],
      ),
      padding: const EdgeInsets.all(28),
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Sign In',
              style: GoogleFonts.inter(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Use * for forgotten characters',
              style: GoogleFonts.inter(
                  fontSize: 13, color: const Color(0xFF64748B)),
            ),
            const SizedBox(height: 28),

            // Username field
            TextFormField(
              controller: _usernameCtrl,
              enabled: !isLoading,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Username',
                prefixIcon: Icon(Icons.person_outline_rounded,
                    color: Color(0xFF6366F1)),
              ),
              validator: (v) =>
                  (v == null || v.isEmpty) ? 'Username required' : null,
            ),
            const SizedBox(height: 16),

            // ECC-aware password field
            EccPasswordField(
              controller: _passwordCtrl,
              enabled: !isLoading,
              label: 'Master Password',
            ),
            const SizedBox(height: 10),

            // ECC budget hint
            _buildEccBudgetHint(),
            const SizedBox(height: 28),

            // Login button
            if (state is AuthFailure)
              _buildErrorBanner(state.message),

            const SizedBox(height: 12),
            GradientButton(
              id: 'btn_login',
              label: isLoading ? 'Authenticating…' : 'Sign In',
              isLoading: isLoading,
              onPressed: isLoading ? null : () => _submit(context),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEccBudgetHint() {
    return AnimatedBuilder(
      animation: _passwordCtrl,
      builder: (_, __) {
        final pw = _passwordCtrl.text;
        final totalLen = pw.length;
        final maxWildcards = totalLen < 8 ? 4 : (totalLen ~/ 4) * 2;
        final maxErrors = maxWildcards ~/ 2;
        
        final e = pw.split('').where((c) => c == '*').length;
        final hint = (e >= maxWildcards)
            ? '⚠  Erasure limit reached ($maxWildcards max)'
            : '✦  $e wildcard${e == 1 ? '' : 's'} — '
                '${maxWildcards - e} remaining  ·  $maxErrors error tolerance';
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            color: const Color(0xFF1E293B),
            border: Border.all(
                color: e >= maxWildcards
                    ? const Color(0xFFEF4444).withOpacity(0.5)
                    : const Color(0xFF6366F1).withOpacity(0.3)),
          ),
          child: Text(
            hint,
            style: GoogleFonts.inter(
              fontSize: 12,
              color: e >= maxWildcards ? const Color(0xFFEF4444) : const Color(0xFF818CF8),
            ),
          ),
        );
      },
    );
  }

  Widget _buildErrorBanner(String message) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      margin: const EdgeInsets.only(bottom: 4),
      decoration: BoxDecoration(
        color: const Color(0xFFEF4444).withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.4)),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded,
              color: Color(0xFFEF4444), size: 18),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: GoogleFonts.inter(fontSize: 13, color: const Color(0xFFEF4444)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRegisterLink(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          "Don't have an account? ",
          style: GoogleFonts.inter(color: const Color(0xFF64748B), fontSize: 14),
        ),
        GestureDetector(
          onTap: () => Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const RegisterScreen()),
          ),
          child: Text(
            'Create one',
            style: GoogleFonts.inter(
              color: const Color(0xFF6366F1),
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }

  void _submit(BuildContext context) {
    if (!_formKey.currentState!.validate()) return;
    context.read<AuthBloc>().add(LoginSubmitted(
          username: _usernameCtrl.text.trim(),
          password: _passwordCtrl.text,
        ));
  }

  void _handleState(BuildContext context, AuthState state) {
    if (state is AuthSuccess) {
      if (state.hadCorrections) {
        _showCorrectionBanner(context, state);
      }
      Navigator.pushReplacementNamed(context, '/vault');
    }
  }

  void _showCorrectionBanner(BuildContext context, AuthSuccess state) {
    final parts = <String>[];
    if (state.correctionsApplied > 0) {
      parts.add('${state.correctionsApplied} error${state.correctionsApplied > 1 ? 's' : ''} corrected');
    }
    if (state.erasuresFilled > 0) {
      parts.add('${state.erasuresFilled} wildcard${state.erasuresFilled > 1 ? 's' : ''} filled');
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.auto_fix_high_rounded,
                color: Color(0xFF6366F1), size: 20),
            const SizedBox(width: 10),
            Text('ECC fixed your password: ${parts.join(', ')}'),
          ],
        ),
        duration: const Duration(seconds: 4),
      ),
    );
  }
}
