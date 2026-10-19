/// B17 فاز ۳۶ — تب سفارش‌های من (/orders با فیلتر خودکار مالک سمت سرور).
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../state/auth_controller.dart';
import '../widgets/empty_state.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key, required this.onError});

  final void Function(Object error) onError;

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  late Future<List<MyOrder>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<MyOrder>> _load() async {
    final client = context.read<AuthController>().api;
    final data = await client.get('/orders');
    final items = data['items'];
    return [
      if (items is List)
        for (final m in items.whereType<Map<String, dynamic>>()) MyOrder.fromMap(m),
    ];
  }

  void _reload() {
    setState(() => _future = _load());
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'paid':
        return Colors.green.shade700;
      case 'pending':
        return Colors.orange.shade800;
      case 'cancelled':
      case 'canceled':
        return Colors.grey.shade600;
      case 'failed':
        return Colors.red.shade700;
      default:
        return Colors.blueGrey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<MyOrder>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) {
          widget.onError(snap.error!);
          return EmptyState(
            message: 'بارگذاری سفارش‌ها ناموفق بود',
            onRetry: _reload,
            isError: true,
          );
        }
        final items = snap.data ?? const <MyOrder>[];
        if (items.isEmpty) {
          return const EmptyState(message: 'سفارشی برای شما ثبت نشده است');
        }
        return RefreshIndicator(
          onRefresh: () async => _reload(),
          child: ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final o = items[i];
              return ListTile(
                leading: const Icon(Icons.receipt_long_outlined),
                title: Text(o.title.isEmpty ? 'سفارش ${o.orderNumber}' : o.title),
                subtitle: Text('شماره: ${o.orderNumber}'),
                trailing: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text('${o.payableAmount}'),
                    Chip(
                      label: Text(o.status,
                          style: const TextStyle(fontSize: 11, color: Colors.white)),
                      backgroundColor: _statusColor(o.status),
                      visualDensity: VisualDensity.compact,
                    ),
                  ],
                ),
              );
            },
          ),
        );
      },
    );
  }
}
