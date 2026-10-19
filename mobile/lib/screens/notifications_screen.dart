/// B17 فاز ۳۶ — تب اعلان‌های من (/notifications) با خواندن/خواندن همه.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../state/auth_controller.dart';
import '../widgets/empty_state.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key, required this.onError});

  final void Function(Object error) onError;

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late Future<_NotifPage> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_NotifPage> _load() async {
    final client = context.read<AuthController>().api;
    final data = await client.get('/notifications');
    final items = data['items'];
    return _NotifPage(
      unread: (data['unread'] ?? 0) as int,
      items: [
        if (items is List)
          for (final m in items.whereType<Map<String, dynamic>>())
            AppNotification.fromMap(m),
      ],
    );
  }

  void _reload() {
    setState(() => _future = _load());
  }

  Future<void> _markRead(AppNotification n) async {
    if (n.isRead) return;
    final client = context.read<AuthController>().api;
    try {
      await client.post('/notifications/${n.id}/read');
      _reload();
    } catch (e) {
      widget.onError(e);
    }
  }

  Future<void> _markAllRead() async {
    final client = context.read<AuthController>().api;
    try {
      await client.post('/notifications/read-all');
      _reload();
    } catch (e) {
      widget.onError(e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<_NotifPage>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          widget.onError(snap.error!);
          return EmptyState(
            message: 'بارگذاری اعلان‌ها ناموفق بود',
            onRetry: _reload,
            isError: true,
          );
        }
        final page = snap.data ?? const _NotifPage(unread: 0, items: []);
        if (page.items.isEmpty) {
          return const EmptyState(message: 'اعلانی برای شما وجود ندارد');
        }
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  Text('${page.unread} اعلان نخوانده'),
                  const Spacer(),
                  TextButton(
                    onPressed: page.unread == 0 ? null : _markAllRead,
                    child: const Text('خواندن همه'),
                  ),
                ],
              ),
            ),
            Expanded(
              child: RefreshIndicator(
                onRefresh: () async => _reload(),
                child: ListView.separated(
                  itemCount: page.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final n = page.items[i];
                    return ListTile(
                      leading: Icon(
                        n.isRead
                            ? Icons.notifications_none
                            : Icons.notifications_active,
                        color: n.severity == 'critical'
                            ? Colors.red
                            : n.severity == 'warning'
                                ? Colors.orange
                                : null,
                      ),
                      title: Text(
                        n.title,
                        style: TextStyle(
                          fontWeight:
                              n.isRead ? FontWeight.w400 : FontWeight.w700,
                        ),
                      ),
                      subtitle: n.body == null ? null : Text(n.body!),
                      isThreeLine: n.body != null && n.body!.length > 44,
                      onTap: () => _markRead(n),
                    );
                  },
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class _NotifPage {
  const _NotifPage({required this.unread, required this.items});
  final int unread;
  final List<AppNotification> items;
}
