import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

const _supabaseUrl = String.fromEnvironment('SUPABASE_URL');
const _supabasePublishableKey =
    String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');

bool get _hasSupabaseConfig =>
    _supabaseUrl.startsWith('https://') &&
    _supabasePublishableKey.isNotEmpty;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  if (_hasSupabaseConfig) {
    await Supabase.initialize(
      url: _supabaseUrl,
      publishableKey: _supabasePublishableKey,
    );
  }

  runApp(const V9OdysseusApp());
}

class V9OdysseusApp extends StatelessWidget {
  const V9OdysseusApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'V9 Odysseus',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF55C6C1),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF0B1220),
        cardTheme: CardThemeData(
          color: const Color(0xFF152238),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
            side: const BorderSide(color: Color(0xFF293B55)),
          ),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: const Color(0xFF111C2E),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      home: !_hasSupabaseConfig
          ? const SetupRequiredPage()
          : const AuthGate(),
    );
  }
}

class SetupRequiredPage extends StatelessWidget {
  const SetupRequiredPage({super.key});

  @override
  Widget build(BuildContext context) {
    return const _StatusScaffold(
      title: 'Konfigurasi diperlukan',
      icon: Icons.settings_outlined,
      message:
          'Fondasi aplikasi sudah tersedia. Tambahkan SUPABASE_URL dan '
          'SUPABASE_PUBLISHABLE_KEY saat proses build untuk mengaktifkan login. '
          'Jangan pernah memasukkan secret key atau kredensial broker ke aplikasi.',
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final client = Supabase.instance.client;
    return StreamBuilder<AuthState>(
      stream: client.auth.onAuthStateChange,
      builder: (context, snapshot) {
        final session = client.auth.currentSession;
        if (session == null) {
          return const SignInPage();
        }
        return ReadOnlyHomePage(email: session.user.email ?? 'Pengguna');
      },
    );
  }
}

class SignInPage extends StatefulWidget {
  const SignInPage({super.key});

  @override
  State<SignInPage> createState() => _SignInPageState();
}

class _SignInPageState extends State<SignInPage> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await Supabase.instance.client.auth.signInWithPassword(
        email: _emailController.text.trim(),
        password: _passwordController.text,
      );
    } on AuthException {
      setState(() {
        _error = 'Login gagal. Periksa email dan kata sandi, lalu coba lagi.';
      });
    } catch (_) {
      setState(() {
        _error = 'Layanan login belum dapat dihubungi. Coba kembali nanti.';
      });
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const _BrandHeader(),
                      const SizedBox(height: 28),
                      Text(
                        'Masuk ke akun',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Akses hanya untuk pengguna yang telah didaftarkan '
                        'oleh administrator proyek.',
                      ),
                      const SizedBox(height: 22),
                      TextFormField(
                        controller: _emailController,
                        keyboardType: TextInputType.emailAddress,
                        autofillHints: const [AutofillHints.username],
                        decoration: const InputDecoration(
                          labelText: 'Email',
                          prefixIcon: Icon(Icons.email_outlined),
                        ),
                        validator: (value) {
                          if (value == null || !value.contains('@')) {
                            return 'Masukkan alamat email yang valid.';
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 14),
                      TextFormField(
                        controller: _passwordController,
                        obscureText: true,
                        autofillHints: const [AutofillHints.password],
                        decoration: const InputDecoration(
                          labelText: 'Kata sandi',
                          prefixIcon: Icon(Icons.lock_outline),
                        ),
                        validator: (value) {
                          if (value == null || value.isEmpty) {
                            return 'Kata sandi wajib diisi.';
                          }
                          return null;
                        },
                        onFieldSubmitted: (_) {
                          if (!_busy) {
                            _signIn();
                          }
                        },
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 14),
                        Text(
                          _error!,
                          style: const TextStyle(color: Colors.redAccent),
                        ),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: _busy ? null : _signIn,
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          child: _busy
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text('Masuk'),
                        ),
                      ),
                      const SizedBox(height: 16),
                      const _ReadOnlyNotice(),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ReadOnlyHomePage extends StatelessWidget {
  const ReadOnlyHomePage({required this.email, super.key});

  final String email;

  Future<void> _signOut() async {
    await Supabase.instance.client.auth.signOut();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('V9 ODYSSEUS'),
        actions: [
          IconButton(
            tooltip: 'Keluar',
            onPressed: _signOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(18),
        children: [
          const _BrandHeader(),
          const SizedBox(height: 20),
          Text('Selamat datang', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(email, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 20),
          const _ReadOnlyNotice(),
          const SizedBox(height: 18),
          const _StatusCard(
            title: 'V9 Trading Engine',
            subtitle: 'Fondasi aplikasi tersedia · koneksi engine belum aktif',
            icon: Icons.insights_outlined,
          ),
          const _StatusCard(
            title: 'Odysseus AI',
            subtitle: 'Pengawasan read-only · tidak memiliki akses eksekusi',
            icon: Icons.psychology_outlined,
          ),
          const _StatusCard(
            title: 'Transaction Control Center',
            subtitle: 'Persetujuan manusia direncanakan · belum terhubung API',
            icon: Icons.fact_check_outlined,
          ),
          const SizedBox(height: 12),
          const Text(
            'Status ini adalah fondasi antarmuka, bukan bukti koneksi broker '
            'atau kesiapan transaksi.',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  const _BrandHeader();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 52,
          height: 52,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: const Color(0xFF173B48),
            borderRadius: BorderRadius.circular(15),
          ),
          child: const Text(
            'V9',
            style: TextStyle(
              fontWeight: FontWeight.w900,
              fontSize: 22,
              color: Color(0xFF9AE8E3),
            ),
          ),
        ),
        const SizedBox(width: 14),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'V9 ODYSSEUS',
                style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1),
              ),
              Text('Capital Protection First', style: TextStyle(fontSize: 12)),
            ],
          ),
        ),
        const _ReadOnlyChip(),
      ],
    );
  }
}

class _ReadOnlyChip extends StatelessWidget {
  const _ReadOnlyChip();

  @override
  Widget build(BuildContext context) {
    return const Chip(
      avatar: Icon(Icons.shield_outlined, size: 15),
      label: Text('READ ONLY'),
      visualDensity: VisualDensity.compact,
    );
  }
}

class _ReadOnlyNotice extends StatelessWidget {
  const _ReadOnlyNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF132B2C),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF2D6660)),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.verified_user_outlined, color: Color(0xFF8BE0C4)),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Mode READ ONLY aktif. Tidak ada koneksi broker, pengiriman order, '
              'atau eksekusi otomatis pada tahap ini.',
            ),
          ),
        ],
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({
    required this.title,
    required this.subtitle,
    required this.icon,
  });

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: Icon(icon, color: const Color(0xFF8BDAD5)),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.lock_outline, size: 18),
      ),
    );
  }
}

class _StatusScaffold extends StatelessWidget {
  const _StatusScaffold({
    required this.title,
    required this.icon,
    required this.message,
  });

  final String title;
  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 480),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const _BrandHeader(),
                    const SizedBox(height: 28),
                    Icon(icon, size: 42, color: const Color(0xFF8BDAD5)),
                    const SizedBox(height: 14),
                    Text(title, style: Theme.of(context).textTheme.titleLarge),
                    const SizedBox(height: 10),
                    Text(message, textAlign: TextAlign.center),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
