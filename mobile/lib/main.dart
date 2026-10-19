/// B17 فاز ۳۶ — نقطه ورود اپ موبایل Rosepsy.
///
/// - Provider برای نشست کاربر؛ بازیابی خودکار توکن پیشین؛
/// - توکن فقط در نشست دستگاه نگه داشته می‌شود و هیچ داده بالینی
///   روی دستگاه ذخیره/کش نمی‌شود (بند حریم خصوصی سند جامع)؛
/// - نشست منقضی (401) → AuthException → خروج خودکار به صفحه ورود.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api/api_client.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'state/auth_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final apiClient = ApiClient();
  final authController = AuthController(apiClient);
  authController.restore();

  runApp(
    MultiProvider(
      providers: [
        Provider<ApiClient>.value(value: apiClient),
        ChangeNotifierProvider<AuthController>.value(value: authController),
      ],
      child: const RosepsyApp(),
    ),
  );
}

class RosepsyApp extends StatelessWidget {
  const RosepsyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF7C4D6D));
    return MaterialApp(
      title: 'Rosepsy',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        fontFamily: 'Vazirmatn',
      ),
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    if (auth.restoring) {
      return const Directionality(
        textDirection: TextDirection.rtl,
        child: Scaffold(
          body: Center(child: CircularProgressIndicator()),
        ),
      );
    }
    return auth.isAuthed ? const HomeScreen() : const LoginScreen();
  }
}
