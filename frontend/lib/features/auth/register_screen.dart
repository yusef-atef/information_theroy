import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../widgets/ecc_password_field.dart';
import '../../widgets/gradient_button.dart';
import 'auth_bloc.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _usernameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  @override
  void dispose() {
    _usernameCtrl.dispose();
    _emailCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => AuthBloc(),
      child: BlocConsumer<AuthBloc, AuthState>(
        listener: _handleState,
        builder: (context, state) {
          final isLoading = state is AuthLoading;
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
                child: Center(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Back arrow
                        Align(
                          alignment: Alignment.centerLeft,
                          child: IconButton(
                            icon: const Icon(Icons.arrow_back_ios_new_rounded,
                                color: Color(0xFF6366F1)),
                            onPressed: () => Navigator.pop(context),
                          ),
                        ),
                        const SizedBox(height: 8),
                        _buildHeader(),
                        const SizedBox(height: 32),
                        _buildCard(context, state, isLoading),
                      ],
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
          width: 60,
          height: 60,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: const LinearGradient(
              colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF6366F1).withOpacity(0.4),
                blurRadius: 20,
                spreadRadius: 2,
              ),
            ],
          ),
          child: const Icon(Icons.person_add_rounded, color: Colors.white, size: 28),
        ),
        const SizedBox(height: 16),
        Text(
          'Create Account',
          style: GoogleFonts.inter(
            fontSize: 26,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'Set your ECC-protected master password',
          style: GoogleFonts.inter(fontSize: 13, color: const Color(0xFF64748B)),
        ),
      ],
    );
  }

  Widget _buildCard(BuildContext context, AuthState state, bool isLoading) {
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
            TextFormField(
              controller: _usernameCtrl,
              enabled: !isLoading,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Username',
                prefixIcon: Icon(Icons.person_outline_rounded,
                    color: Color(0xFF6366F1)),
              ),
              validator: (v) {
                if (v == null || v.isEmpty) return 'Username required';
                if (v.length < 3) return 'At least 3 characters';
                return null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _emailCtrl,
              enabled: !isLoading,
              keyboardType: TextInputType.emailAddress,
              style: const TextStyle(color: Colors.white),
              decoration: const InputDecoration(
                labelText: 'Email',
                prefixIcon:
                    Icon(Icons.email_outlined, color: Color(0xFF6366F1)),
              ),
              validator: (v) {
                if (v == null || v.isEmpty) return 'Email required';
                if (!v.contains('@')) return 'Invalid email';
                return null;
              },
            ),
            const SizedBox(height: 16),

            EccPasswordField(
              controller: _passwordCtrl,
              enabled: !isLoading,
              label: 'Master Password',
              allowWildcards: false, // no wildcards at registration
            ),

            const SizedBox(height: 10),
            _buildPasswordStrengthHint(),
            const SizedBox(height: 28),

            if (state is AuthFailure)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEF4444).withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                        color: const Color(0xFFEF4444).withOpacity(0.4)),
                  ),
                  child: Text(state.message,
                      style: const TextStyle(color: Color(0xFFEF4444))),
                ),
              ),

            GradientButton(
              id: 'btn_register',
              label: isLoading ? 'Creating Account…' : 'Create Account',
              isLoading: isLoading,
              onPressed: isLoading ? null : () => _submit(context),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPasswordStrengthHint() {
    return AnimatedBuilder(
      animation: _passwordCtrl,
      builder: (_, __) {
        final pw = _passwordCtrl.text;
        final len = pw.length;
        final strength = len < 6
            ? 0
            : len < 10
                ? 1
                : 2;
        final labels = ['Weak', 'Good', 'Strong'];
        final colors = [
          const Color(0xFFEF4444),
          const Color(0xFFF59E0B),
          const Color(0xFF10B981),
        ];
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: List.generate(
                3,
                (i) => Expanded(
                  child: Container(
                    margin: const EdgeInsets.only(right: 4),
                    height: 4,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(4),
                      color: i <= strength
                          ? colors[strength]
                          : const Color(0xFF1E293B),
                    ),
                  ),
                ),
              ),
            ),
            if (len > 0)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  '${labels[strength]} — $len / 64 characters',
                  style: GoogleFonts.inter(
                      fontSize: 12, color: colors[strength]),
                ),
              ),
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text(
                '* character NOT allowed in registration password',
                style: GoogleFonts.inter(
                    fontSize: 11, color: const Color(0xFF64748B)),
              ),
            ),
          ],
        );
      },
    );
  }

  void _submit(BuildContext context) {
    if (!_formKey.currentState!.validate()) return;
    if (_passwordCtrl.text.contains('*')) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Wildcard * not allowed at registration')),
      );
      return;
    }
    context.read<AuthBloc>().add(RegisterSubmitted(
          username: _usernameCtrl.text.trim(),
          email: _emailCtrl.text.trim(),
          password: _passwordCtrl.text,
        ));
  }

  void _handleState(BuildContext context, AuthState state) {
    if (state is RegisterSuccess) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle_outline_rounded,
                  color: Color(0xFF10B981), size: 20),
              const SizedBox(width: 10),
              Text('Account created! Welcome, ${state.username}'),
            ],
          ),
          backgroundColor: const Color(0xFF1A2235),
        ),
      );
      Navigator.pop(context);
    }
  }
}
