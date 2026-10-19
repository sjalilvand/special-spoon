/// B17 فاز ۳۶ — صفحه اصلی اپ با چهار تب: پروفایل/نوبت‌ها/اعلان‌ها/سفارش‌ها.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../screens/appointments_screen.dart';
import '../screens/notifications_screen.dart';
import '../screens/orders_screen.dart';
import '../screens/profile_screen.dart';
import '../state/auth_controller.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = 0;

  void _onAuthError(BuildContext context, Object error) {
    if (error is AuthException) {
      context.read<AuthController>().logout();
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$error'), backgroundColor: Colors.red.shade700),
    );
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    final pages = [
      ProfileScreen(onError: (e) => _onAuthError(context, e)),
      AppointmentsScreen(onError: (e) => _onAuthError(context, e)),
      NotificationsScreen(onError: (e) => _onAuthError(context, e)),
      OrdersScreen(onError: (e) => _onAuthError(context, e)),
    ];
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Rosepsy'),
          actions: [
            IconButton(
              tooltip: 'خروج',
              icon: const Icon(Icons.logout),
              onPressed: () => context.read<AuthController>().logout(),
            ),
          ],
        ),
        body: IndexedStack(index: _index, children: pages),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: (i) => setState(() => _index = i),
          destinations: const [
            NavigationDestination(icon: Icon(Icons.person_outline), label: 'پروفایل'),
            NavigationDestination(
                icon: Icon(Icons.event_note_outlined), label: 'نوبت‌های من'),
            NavigationDestination(
                icon: Icon(Icons.notifications_outlined), label: 'اعلان‌ها'),
            NavigationDestination(
                icon: Icon(Icons.receipt_long_outlined), label: 'سفارش‌ها'),
          ],
        ),
      ),
    );
  }
}
