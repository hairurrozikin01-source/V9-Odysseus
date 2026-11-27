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
          'Tambahkan SUPABASE_URL dan SUPABASE_PUBLISHABLE_KEY saat proses '
          'build. Gunakan publishable key saja; jangan pernah memasukkan '
          'secret key atau kredensial broker ke aplikasi.',
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
        if (session == null) return const SignInPage();
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
    } on AuthException catch (e) {
      if (!mounted) return;
      final detail = e.message.trim();
      final status = e.statusCode;
      setState(() {
        _error = status == null
            ? 'Login gagal: $detail'
            : 'Login gagal (HTTP $status): $detail';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Layanan login belum dapat dihubungi. Coba kembali nanti.';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
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
                      Text('Masuk ke akun',
                          style: Theme.of(context).textTheme.headlineSmall),
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
                        validator: (value) => value == null || value.isEmpty
                            ? 'Kata sandi wajib diisi.'
                            : null,
                        onFieldSubmitted: (_) {
                          if (!_busy) _signIn();
                        },
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 14),
                        Text(_error!,
                            style:
                                const TextStyle(color: Colors.redAccent)),
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
                                      strokeWidth: 2),
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

class ReadOnlyHomePage extends StatefulWidget {
  const ReadOnlyHomePage({required this.email, super.key});
  final String email;

  @override
  State<ReadOnlyHomePage> createState() => _ReadOnlyHomePageState();
}

class _ReadOnlyHomePageState extends State<ReadOnlyHomePage> {
  int _selectedIndex = 0;

  Future<void> _signOut() async {
    await Supabase.instance.client.auth.signOut();
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      OverviewPage(email: widget.email, onOpenTab: (index) {
        setState(() => _selectedIndex = index);
      }),
      const MarketSignalsPage(),
      const RiskMonitoringPage(),
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('V9 ODYSSEUS'),
        actions: [
          const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: _ReadOnlyChip(),
          ),
          IconButton(
            tooltip: 'Keluar',
            onPressed: _signOut,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: IndexedStack(
        index: _selectedIndex,
        children: pages,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: (index) =>
            setState(() => _selectedIndex = index),
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.dashboard_outlined),
              selectedIcon: Icon(Icons.dashboard),
              label: 'Ringkasan'),
          NavigationDestination(
              icon: Icon(Icons.show_chart), label: 'Sinyal'),
          NavigationDestination(
              icon: Icon(Icons.shield_outlined), label: 'Risiko'),
        ],
      ),
    );
  }
}

class OverviewPage extends StatelessWidget {
  const OverviewPage({required this.email, required this.onOpenTab, super.key});
  final String email;
  final ValueChanged<int> onOpenTab;

  Future<Map<String, dynamic>> _loadIdentity() async {
    final client = Supabase.instance.client;
    final userId = client.auth.currentUser!.id;
    final profile = await client
        .from('profiles')
        .select('display_name')
        .eq('user_id', userId)
        .maybeSingle();
    final role = await client
        .from('user_roles')
        .select('role')
        .eq('user_id', userId)
        .maybeSingle();
    return {'display_name': profile?['display_name'], 'role': role?['role']};
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(18),
      children: [
        const _BrandHeader(),
        const SizedBox(height: 20),
        Text('Selamat datang',
            style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 4),
        Text(email, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 16),
        FutureBuilder<Map<String, dynamic>>(
          future: _loadIdentity(),
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return const _InfoCard(
                title: 'Profil dan peran',
                message:
                    'Data profil belum dapat dibaca. Periksa koneksi atau izin akses.',
                icon: Icons.person_outline,
              );
            }
            if (!snapshot.hasData) {
              return const LinearProgressIndicator();
            }
            final data = snapshot.data!;
            final name = data['display_name'] as String?;
            final role = data['role'] as String?;
            return _InfoCard(
              title: name?.isNotEmpty == true ? name! : 'Akun pengguna',
              message: 'Hak akses: ${role ?? 'belum terdata'}',
              icon: Icons.verified_user_outlined,
            );
          },
        ),
        const SizedBox(height: 14),
        const _ReadOnlyNotice(),
        const SizedBox(height: 18),
        _NavigationCard(
          title: 'Market Intelligence',
          subtitle:
              'Lihat sinyal pasar yang tersimpan di database. Tidak membuat order.',
          icon: Icons.show_chart,
          onTap: () => onOpenTab(1),
        ),
        _NavigationCard(
          title: 'Risk Monitoring',
          subtitle:
              'Pantau penilaian risiko milik akun ini dan keputusan sistem.',
          icon: Icons.shield_outlined,
          onTap: () => onOpenTab(2),
        ),
        const SizedBox(height: 12),
        const _InfoCard(
          title: 'Odysseus AI',
          message:
              'Panel ini belum menjalankan model AI atau menghasilkan rekomendasi baru. '
              'Saat ini hanya menampilkan data yang sudah tersimpan.',
          icon: Icons.psychology_outlined,
        ),
        const SizedBox(height: 12),
        const Text(
          'Mode READ ONLY aktif. Tidak ada koneksi broker, pengiriman order, '
          'atau eksekusi otomatis.',
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

class MarketSignalsPage extends StatefulWidget {
  const MarketSignalsPage({super.key});

  @override
  State<MarketSignalsPage> createState() => _MarketSignalsPageState();
}

class _MarketSignalsPageState extends State<MarketSignalsPage> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = _loadSignals();
  }

  Future<List<Map<String, dynamic>>> _loadSignals() async {
    final rows = await Supabase.instance.client
        .from('market_signals')
        .select(
            'id,symbol,market,timeframe,direction,confidence,strategy,rationale,created_at')
        .order('created_at', ascending: false)
        .limit(30);
    return rows.map((row) => Map<String, dynamic>.from(row)).toList();
  }

  void _refresh() => setState(() => _future = _loadSignals());

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _refresh(),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(18),
        children: [
          Text('Market Intelligence',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 6),
          const Text(
            'Sinyal yang sudah tersimpan. Data kosong berarti belum ada sinyal '
            'yang dikirim ke database.',
          ),
          const SizedBox(height: 14),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(
                    child: Padding(
                        padding: EdgeInsets.all(28),
                        child: CircularProgressIndicator()));
              }
              if (snapshot.hasError) {
                return _LoadError(message: _safeError(snapshot.error),
                    onRetry: _refresh);
              }
              final rows = snapshot.data ?? [];
              if (rows.isEmpty) {
                return const MarketEmptyState();
              }
              return Column(
                children: rows.map((row) => _SignalCard(row: row)).toList(),
              );
            },
          ),
        ],
      ),
    );
  }
}

class RiskMonitoringPage extends StatefulWidget {
  const RiskMonitoringPage({super.key});

  @override
  State<RiskMonitoringPage> createState() => _RiskMonitoringPageState();
}

class _RiskMonitoringPageState extends State<RiskMonitoringPage> {
  late Future<List<Map<String, dynamic>>> _future;

  @override
  void initState() {
    super.initState();
    _future = _loadAssessments();
  }

  Future<List<Map<String, dynamic>>> _loadAssessments() async {
    final rows = await Supabase.instance.client
        .from('risk_assessments')
        .select(
            'id,signal_id,risk_level,decision,rationale,assessment_payload,created_at')
        .order('created_at', ascending: false)
        .limit(30);
    return rows.map((row) => Map<String, dynamic>.from(row)).toList();
  }

  void _refresh() => setState(() => _future = _loadAssessments());

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _refresh(),
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(18),
        children: [
          Text('Risk Monitoring',
              style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 6),
          const Text(
            'Penilaian risiko yang tersimpan untuk akun ini. Panel ini tidak '
            'mengubah batas risiko atau membuka transaksi.',
          ),
          const SizedBox(height: 14),
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _future,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(
                    child: Padding(
                        padding: EdgeInsets.all(28),
                        child: CircularProgressIndicator()));
              }
              if (snapshot.hasError) {
                return _LoadError(message: _safeError(snapshot.error),
                    onRetry: _refresh);
              }
              final rows = snapshot.data ?? [];
              if (rows.isEmpty) {
                return const RiskEmptyState();
              }
              return Column(
                children: rows.map((row) => _RiskCard(row: row)).toList(),
              );
            },
          ),
        ],
      ),
    );
  }
}

class MarketEmptyState extends StatelessWidget {
  const MarketEmptyState({super.key});

  @override
  Widget build(BuildContext context) => const _EmptyState(
        title: 'Belum ada sinyal pasar',
        message:
            'Database belum memiliki sinyal. V9 belum menerima atau menghasilkan '
            'data market pada tahap ini.',
        icon: Icons.query_stats_outlined,
      );
}

class RiskEmptyState extends StatelessWidget {
  const RiskEmptyState({super.key});

  @override
  Widget build(BuildContext context) => const _EmptyState(
        title: 'Belum ada penilaian risiko',
        message:
            'Belum ada risk assessment tersimpan untuk akun ini. Tidak ada '
            'risiko transaksi yang sedang dihitung oleh aplikasi.',
        icon: Icons.shield_outlined,
      );
}

class _SignalCard extends StatelessWidget {
  const _SignalCard({required this.row});
  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    final confidence = row['confidence'];
    final confidenceText = confidence == null ? '—' : confidence.toString();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(
                child: Text(
                  '${row['symbol']} · ${row['market']}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
              Text('${row['direction']}'),
            ]),
            const SizedBox(height: 6),
            Text('Timeframe: ${row['timeframe']}  •  Confidence: $confidenceText'),
            if (row['strategy'] != null) Text('Strategi: ${row['strategy']}'),
            if (row['rationale'] != null) ...[
              const SizedBox(height: 6),
              Text('${row['rationale']}'),
            ],
            const SizedBox(height: 8),
            Text(_formatDate(row['created_at']),
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _RiskCard extends StatelessWidget {
  const _RiskCard({required this.row});
  final Map<String, dynamic> row;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Expanded(
                child: Text('Risiko: ${row['risk_level']}',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
              ),
              Text('${row['decision']}'),
            ]),
            const SizedBox(height: 6),
            Text('${row['rationale']}'),
            const SizedBox(height: 8),
            Text(_formatDate(row['created_at']),
                style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _LoadError extends StatelessWidget {
  const _LoadError({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) => _InfoCard(
        title: 'Data belum dapat dimuat',
        message: message,
        icon: Icons.cloud_off_outlined,
        action: TextButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Coba lagi'),
        ),
      );
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.title,
    required this.message,
    required this.icon,
  });
  final String title;
  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(22),
          child: Column(
            children: [
              Icon(icon, size: 38, color: const Color(0xFF8BDAD5)),
              const SizedBox(height: 10),
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              Text(message, textAlign: TextAlign.center),
            ],
          ),
        ),
      );
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({
    required this.title,
    required this.message,
    required this.icon,
    this.action,
  });
  final String title;
  final String message;
  final IconData icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Icon(icon, color: const Color(0xFF8BDAD5)),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(title,
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              ]),
              const SizedBox(height: 8),
              Text(message),
              if (action != null) Align(
                alignment: Alignment.centerRight,
                child: action!,
              ),
            ],
          ),
        ),
      );
}

class _NavigationCard extends StatelessWidget {
  const _NavigationCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });
  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: Icon(icon, color: const Color(0xFF8BDAD5)),
          title: Text(title),
          subtitle: Text(subtitle),
          trailing: const Icon(Icons.chevron_right),
          onTap: onTap,
        ),
      );
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
              Text('V9 ODYSSEUS',
                  style: TextStyle(
                      fontWeight: FontWeight.bold, letterSpacing: 1)),
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
  Widget build(BuildContext context) => const Chip(
        avatar: Icon(Icons.shield_outlined, size: 15),
        label: Text('READ ONLY'),
        visualDensity: VisualDensity.compact,
      );
}

class _ReadOnlyNotice extends StatelessWidget {
  const _ReadOnlyNotice();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF132B2C),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF2D6660)),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.verified_user_outlined,
                color: Color(0xFF8BE0C4)),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Mode READ ONLY aktif. Tidak ada koneksi broker, pengiriman '
                'order, atau eksekusi otomatis pada tahap ini.',
              ),
            ),
          ],
        ),
      );
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
  Widget build(BuildContext context) => Scaffold(
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
                      Icon(icon, size: 42,
                          color: const Color(0xFF8BDAD5)),
                      const SizedBox(height: 14),
                      Text(title,
                          style: Theme.of(context).textTheme.titleLarge),
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

String _formatDate(dynamic value) {
  if (value == null) return 'Waktu tidak tersedia';
  final parsed = DateTime.tryParse(value.toString());
  if (parsed == null) return value.toString();
  final local = parsed.toLocal();
  return '${local.day.toString().padLeft(2, '0')}/'
      '${local.month.toString().padLeft(2, '0')}/'
      '${local.year} ${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}

String _safeError(Object? error) {
  final message = error?.toString() ?? 'Kesalahan tidak diketahui';
  if (message.length > 180) return '${message.substring(0, 180)}…';
  return message;
}
