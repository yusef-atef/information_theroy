import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../core/models/file_item.dart';
import '../../features/auth/auth_bloc.dart';
import 'vault_bloc.dart';
import 'file_card.dart';
import 'file_preview_screen.dart';

class VaultScreen extends StatelessWidget {
  const VaultScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(create: (_) => VaultBloc()..add(LoadFiles())),
        BlocProvider(create: (_) => AuthBloc()),
      ],
      child: const _VaultView(),
    );
  }
}

class _VaultView extends StatelessWidget {
  const _VaultView();

  @override
  Widget build(BuildContext context) {
    return BlocListener<AuthBloc, AuthState>(
      listener: (context, state) {
        if (state is AuthInitial) {
          Navigator.pushReplacementNamed(context, '/login');
        }
        if (state is AuthFailure) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(state.message)),
          );
        }
      },
      child: BlocConsumer<VaultBloc, VaultState>(
        listener: (context, state) {
          if (state is VaultError) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Row(children: [
                  const Icon(Icons.error_outline_rounded,
                      color: Color(0xFFEF4444), size: 18),
                  const SizedBox(width: 10),
                  Expanded(child: Text(state.message)),
                ]),
              ),
            );
          }
          if (state is VaultOperationSuccess) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Row(children: [
                  const Icon(Icons.check_circle_outline_rounded,
                      color: Color(0xFF10B981), size: 18),
                  const SizedBox(width: 10),
                  Text(state.message),
                ]),
              ),
            );
          }
          if (state is VaultPreviewReady) {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => FilePreviewScreen(
                  bytes: state.bytes,
                  filename: state.filename,
                ),
              ),
            );
          }
        },
        builder: (context, state) {
          return Scaffold(
            backgroundColor: const Color(0xFF0A0E1A),
            body: CustomScrollView(
              slivers: [
                _buildAppBar(context),
                _buildBody(context, state),
              ],
            ),
            floatingActionButton: _buildFab(context, state),
          );
        },
      ),
    );
  }

  // -------------------------------------------------------------------------
  // App Bar
  // -------------------------------------------------------------------------
  SliverAppBar _buildAppBar(BuildContext context) {
    return SliverAppBar(
      expandedHeight: 160,
      pinned: true,
      backgroundColor: const Color(0xFF0A0E1A),
      elevation: 0,
      automaticallyImplyLeading: false,
      flexibleSpace: FlexibleSpaceBar(
        background: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFF1E1B4B), Color(0xFF0A0E1A)],
            ),
          ),
          child: SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      // Logo
                      Row(
                        children: [
                          Container(
                            width: 38,
                            height: 38,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(
                                colors: [Color(0xFF6366F1), Color(0xFF8B5CF6)],
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color:
                                      const Color(0xFF6366F1).withOpacity(0.4),
                                  blurRadius: 12,
                                  spreadRadius: 2,
                                ),
                              ],
                            ),
                            child: const Icon(Icons.shield_rounded,
                                color: Colors.white, size: 20),
                          ),
                          const SizedBox(width: 10),
                          Text(
                            'SecureCorrect',
                            style: GoogleFonts.inter(
                              fontSize: 18,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                      // Actions Menu
                      PopupMenuButton<String>(
                        icon: const Icon(Icons.more_vert_rounded, color: Color(0xFF64748B)),
                        color: const Color(0xFF1A2235),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        onSelected: (value) {
                          if (value == 'logout') {
                            context.read<AuthBloc>().add(LogoutRequested());
                          } else if (value == 'delete') {
                            _confirmDeleteAccount(context);
                          }
                        },
                        itemBuilder: (context) => [
                          PopupMenuItem(
                            value: 'logout',
                            child: Row(
                              children: [
                                const Icon(Icons.logout_rounded, color: Color(0xFF64748B), size: 20),
                                const SizedBox(width: 12),
                                Text('Logout', style: GoogleFonts.inter(color: Colors.white)),
                              ],
                            ),
                          ),
                          PopupMenuItem(
                            value: 'delete',
                            child: Row(
                              children: [
                                const Icon(Icons.delete_forever_rounded, color: Color(0xFFEF4444), size: 20),
                                const SizedBox(width: 12),
                                Text('Delete Account', style: GoogleFonts.inter(color: Color(0xFFEF4444))),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'Your Vault',
                    style: GoogleFonts.inter(
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'All files encrypted with AES-256-GCM',
                    style: GoogleFonts.inter(
                        fontSize: 13, color: const Color(0xFF64748B)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  // -------------------------------------------------------------------------
  // Body
  // -------------------------------------------------------------------------
  Widget _buildBody(BuildContext context, VaultState state) {
    if (state is VaultLoading || state is VaultInitial) {
      return const SliverFillRemaining(
        child: Center(
          child: CircularProgressIndicator(color: Color(0xFF6366F1)),
        ),
      );
    }

    if (state is VaultUploading) {
      return SliverFillRemaining(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 120,
                height: 120,
                child: CircularProgressIndicator(
                  value: state.progress,
                  color: const Color(0xFF6366F1),
                  strokeWidth: 6,
                  backgroundColor: const Color(0xFF1E293B),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Encrypting & uploading…',
                style: GoogleFonts.inter(
                    color: const Color(0xFF94A3B8), fontSize: 16),
              ),
            ],
          ),
        ),
      );
    }

    final files = switch (state) {
      VaultLoaded s => s.files,
      VaultOperationSuccess s => s.files,
      _ => <FileItem>[],
    };

    if (files.isEmpty) {
      return SliverFillRemaining(child: _buildEmptyState());
    }

    return SliverPadding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
      sliver: SliverList(
        delegate: SliverChildBuilderDelegate(
          (context, index) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: FileCard(
              file: files[index],
              onDownload: () => context
                  .read<VaultBloc>()
                  .add(DownloadFileRequested(files[index])),
              onDelete: () => _confirmDelete(context, files[index]),
            ),
          ),
          childCount: files.length,
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 96,
            height: 96,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: const Color(0xFF1E293B),
              border: Border.all(
                  color: const Color(0xFF334155), width: 1.5),
            ),
            child: const Icon(Icons.cloud_upload_outlined,
                color: Color(0xFF475569), size: 44),
          ),
          const SizedBox(height: 20),
          Text(
            'Your vault is empty',
            style: GoogleFonts.inter(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: const Color(0xFFCBD5E1)),
          ),
          const SizedBox(height: 8),
          Text(
            'Tap ＋ to upload your first encrypted file',
            style: GoogleFonts.inter(
                fontSize: 14, color: const Color(0xFF64748B)),
          ),
        ],
      ),
    );
  }

  // -------------------------------------------------------------------------
  // FAB
  // -------------------------------------------------------------------------
  Widget _buildFab(BuildContext context, VaultState state) {
    final busy = state is VaultLoading || state is VaultUploading;
    return FloatingActionButton.extended(
      onPressed: busy
          ? null
          : () => context.read<VaultBloc>().add(UploadFileRequested()),
      backgroundColor: const Color(0xFF6366F1),
      icon: busy
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                  color: Colors.white, strokeWidth: 2),
            )
          : const Icon(Icons.add_rounded, color: Colors.white),
      label: Text(
        busy ? 'Working…' : 'Upload File',
        style: GoogleFonts.inter(
            fontWeight: FontWeight.w600, color: Colors.white),
      ),
      elevation: 4,
    );
  }

  // -------------------------------------------------------------------------
  // Delete confirmation
  // -------------------------------------------------------------------------
  void _confirmDelete(BuildContext context, FileItem file) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1A2235),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Delete File',
            style: GoogleFonts.inter(
                color: Colors.white, fontWeight: FontWeight.w700)),
        content: Text(
          'Delete "${file.filename}"?\nThis cannot be undone.',
          style: GoogleFonts.inter(color: const Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel',
                style: GoogleFonts.inter(color: const Color(0xFF6366F1))),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFEF4444),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(context);
              context
                  .read<VaultBloc>()
                  .add(DeleteFileRequested(file.id));
            },
            child: Text('Delete',
                style: GoogleFonts.inter(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteAccount(BuildContext context) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: const Color(0xFF1A2235),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Text('Delete Account',
            style: GoogleFonts.inter(
                color: Colors.white, fontWeight: FontWeight.w700)),
        content: Text(
          'Are you absolutely sure? This will PERMANENTLY delete your account and all your encrypted files.\n\nThis action cannot be undone.',
          style: GoogleFonts.inter(color: const Color(0xFF94A3B8)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel',
                style: GoogleFonts.inter(color: const Color(0xFF6366F1))),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFEF4444),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
            onPressed: () {
              Navigator.pop(context);
              context
                  .read<AuthBloc>()
                  .add(AccountDeletionRequested());
            },
            child: Text('Permanently Delete',
                style: GoogleFonts.inter(color: Colors.white)),
          ),
        ],
      ),
    );
  }
}
