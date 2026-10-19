/// B17 فاز ۳۶ — تب نوبت‌های من (/me/appointments).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../state/auth_controller.dart';
import '../widgets/empty_state.dart';

class AppointmentsScreen extends StatefulWidget {
  const AppointmentsScreen({super.key, required this.onError});

  final void Function(Object error) onError;

  @override
  State<AppointmentsScreen> createState() => _AppointmentsScreenState();
}

class _AppointmentsScreenState extends State<AppointmentsScreen> {
  late Future<List<MyAppointment>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<MyAppointment>> _load() async {
    final client = context.read<AuthController>().api;
    final data = await client.get('/me/appointments');
    final items = data['items'];
    return [
      if (items is List)
        for (final m in items.whereType<Map<String, dynamic>>())
          MyAppointment.fromMap(m),
    ];
  }

  void _reload() {
    setState(() => _future = _load());
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MyAppointment>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          widget.onError(snap.error!);
          return EmptyState(
            message: 'بارگذاری نوبت‌ها ناموفق بود',
            onRetry: _reload,
            isError: true,
          );
        }
        final items = snap.data ?? const <MyAppointment>[];
        if (items.isEmpty) {
          return const EmptyState(message: 'هنوز نوبتی برای شما ثبت نشده است');
        }
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final a = items[i];
              return ListTile(
                leading: const Icon(Icons.event_note_outlined),
                title: Text('پرونده ${a.caseNumber}'),
                subtitle: Text(
                    'زمان: ${a.scheduledAt}${a.location == null ? '' : '\nمحل: ${a.location}'}'),
                isThreeLine: a.location != null,
                trailing: Chip(
                    label: Text(a.status), visualDensity: VisualDensity.compact),
              );
            },
          ),
        );
      },
    );
  }
}
