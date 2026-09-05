# Frontend

## Overview

Frontend RusEquity Terminal разрабатывается на **Flutter** с единой кодовой базой для всех платформ.

---

## Platform Support

### Target Platforms

| Platform | Status | Notes |
|----------|--------|-------|
| iOS      | ⏳ Planned | iPhone, iPad |
| Android  | ⏳ Planned | Phone, Tablet |
| Windows  | ⏳ Planned | Desktop app |
| macOS    | ⏳ Planned | Desktop app |
| Linux    | ⏳ Planned | Desktop app |
| Web      | 🔮 Future  | Phase 4+ |

### Cross-Platform Requirements

**Критично:** Один codebase для телефона и компьютера.

- Адаптивный UI под разные размеры экранов
- Responsive layouts
- Platform-specific adaptations где необходимо
- Единая бизнес-логика

---

## Architecture

### Folder Structure

```
lib/
├── main.dart                  # Entry point
├── app/
│   ├── app.dart               # MaterialApp configuration
│   ├── routes.dart            # Route definitions
│   └── theme/
│       ├── app_theme.dart     # Theme data
│       ├── colors.dart        # Color palette
│       └── typography.dart    # Text styles
│
├── features/
│   ├── stocks/
│   │   ├── presentation/
│   │   │   ├── stock_list_screen.dart
│   │   │   ├── stock_detail_screen.dart
│   │   │   └── widgets/
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   └── repositories/
│   │   └── data/
│   │       ├── datasources/
│   │       └── models/
│   │
│   ├── analytics/
│   │   ├── presentation/
│   │   │   ├── analytics_dashboard.dart
│   │   │   ├── valuation_view.dart
│   │   │   ├── factors_view.dart
│   │   │   └── widgets/
│   │   └── ...
│   │
│   ├── portfolio/
│   │   └── ...
│   │
│   └── ai_insights/
│       └── ...
│
├── shared/
│   ├── widgets/
│   │   ├── common/
│   │   │   ├── app_button.dart
│   │   │   ├── app_text_field.dart
│   │   │   └── loading_indicator.dart
│   │   ├── charts/
│   │   │   ├── price_chart.dart
│   │   │   ├── bar_chart.dart
│   │   │   └── pie_chart.dart
│   │   └── cards/
│   │       ├── stock_card.dart
│   │       └── metric_card.dart
│   │
│   ├── utils/
│   │   ├── formatters.dart
│   │   ├── validators.dart
│   │   └── extensions.dart
│   │
│   └── constants/
│       ├── api_endpoints.dart
│       └── app_constants.dart
│
└── services/
    ├── api_client.dart        # HTTP client
    ├── storage.dart           # Local storage
    ├── auth.dart              # Authentication
    └── di.dart                # Dependency injection
```

---

## State Management

### Recommended: Riverpod

```dart
// features/stocks/presentation/providers/stock_providers.dart

import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'stock_providers.g.dart';

@riverpod
Future<List<Stock>> stocks(StocksRef ref) {
  final repository = ref.watch(stockRepositoryProvider);
  return repository.getAll();
}

@riverpod
class StockDetail extends _$StockDetail {
  @override
  Future<Stock?> build(String ticker) async {
    final repository = ref.read(stockRepositoryProvider);
    return repository.getByTicker(ticker);
  }
  
  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() => 
      ref.read(stockRepositoryProvider).getByTicker(ticker)
    );
  }
}
```

### Alternative: Bloc

```dart
// features/stocks/presentation/bloc/stock_bloc.dart

class StockBloc extends Bloc<StockEvent, StockState> {
  final StockRepository repository;
  
  StockBloc(this.repository) : super(StockInitial()) {
    on<LoadStocks>(_onLoadStocks);
    on<LoadStockDetail>(_onLoadStockDetail);
  }
  
  Future<void> _onLoadStocks(
    LoadStocks event,
    Emitter<StockState> emit,
  ) async {
    emit(StockLoading());
    try {
      final stocks = await repository.getAll();
      emit(StocksLoaded(stocks));
    } catch (e) {
      emit(StockError(e.toString()));
    }
  }
}
```

---

## Key Screens

### 1. Stock List Screen

**Purpose:** Display list of all stocks with key metrics

**Features:**
- Search/filter
- Sort by various metrics
- Pull to refresh
- Infinite scroll
- Quick actions (add to watchlist)

**Layout:**
```
┌─────────────────────────────────┐
│ [Search Bar]              [Filter]│
├─────────────────────────────────┤
│ SBER  285.50  +2.3%  P/E: 5.2   │
│ GAZP  168.20  -0.5%  P/E: 4.1   │
│ LKOH  6850.0  +1.1%  P/E: 6.8   │
│ ...                             │
└─────────────────────────────────┘
```

### 2. Stock Detail Screen

**Purpose:** Comprehensive view of single stock

**Features:**
- Price chart (interactive)
- Key metrics cards
- Valuation analysis
- Dividend history
- AI summary
- Related news

**Layout (Desktop):**
```
┌──────────────────────────────────────────────────────┐
│ ← SBER  Sberbank                    [+ Watchlist]   │
├──────────────────────┬───────────────────────────────┤
│                      │  Key Metrics                 │
│   [Price Chart]      │  P/E    P/B    ROE   DivYld  │
│                      │  5.2    0.8    15%   8.5%    │
│                      ├───────────────────────────────┤
│                      │  Valuation                   │
│  [Dividend Chart]    │  Percentiles...              │
│                      ├───────────────────────────────┤
│                      │  AI Insight                  │
│                      │  "Компания торгуется ниже..." │
└──────────────────────┴───────────────────────────────┘
```

**Layout (Mobile):**
```
┌─────────────────┐
│ ← SBER          │
├─────────────────┤
│   [Chart]       │
├─────────────────┤
│ Key Metrics     │
│ [Horizontal     │
│  Scroll]        │
├─────────────────┤
│ Valuation       │
├─────────────────┤
│ AI Insight      │
└─────────────────┘
```

### 3. Analytics Dashboard

**Purpose:** Portfolio/screening analytics

**Features:**
- Factor scores visualization
- Screening results
- Comparison tools
- Export functionality

### 4. AI Insights Screen

**Purpose:** AI-generated analysis and Q&A

**Features:**
- Chat interface
- Stock summaries
- Financial Q&A
- Alert explanations

---

## Responsive Design

### Breakpoints

```dart
// shared/utils/responsive.dart

class Breakpoints {
  static const double mobile = 600;
  static const double tablet = 900;
  static const double desktop = 1200;
}

enum DeviceType {
  mobile,
  tablet,
  desktop,
}

DeviceType getDeviceType(double width) {
  if (width < Breakpoints.mobile) return DeviceType.mobile;
  if (width < Breakpoints.tablet) return DeviceType.tablet;
  return DeviceType.desktop;
}
```

### Adaptive Layouts

```dart
// Example: Adaptive grid

LayoutBuilder(
  builder: (context, constraints) {
    final deviceType = getDeviceType(constraints.maxWidth);
    
    int crossAxisCount;
    switch (deviceType) {
      case DeviceType.mobile:
        crossAxisCount = 1;
        break;
      case DeviceType.tablet:
        crossAxisCount = 2;
        break;
      case DeviceType.desktop:
        crossAxisCount = 3;
        break;
    }
    
    return GridView.count(
      crossAxisCount: crossAxisCount,
      children: [...],
    );
  },
)
```

---

## Packages

### Core Dependencies

```yaml
# pubspec.yaml

dependencies:
  flutter:
    sdk: flutter
  
  # State Management
  flutter_riverpod: ^2.4.0
  riverpod_annotation: ^2.3.0
  
  # Navigation
  go_router: ^12.0.0
  
  # Networking
  dio: ^5.3.0
  retrofit: ^4.0.0
  
  # Local Storage
  hive: ^2.2.0
  hive_flutter: ^1.1.0
  
  # Charts
  fl_chart: ^0.64.0
  candlesticks: ^2.1.0
  
  # UI Components
  flutter_staggered_grid_view: ^0.7.0
  pull_to_refresh: ^2.0.0
  
  # Utilities
  intl: ^0.18.0
  json_annotation: ^4.8.0
  equatable: ^2.0.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
  riverpod_generator: ^2.3.0
  retrofit_generator: ^8.0.0
  json_serializable: ^6.7.0
  hive_generator: ^2.0.0
```

---

## Testing

### Unit Tests

```dart
// test/features/stocks/stock_detail_test.dart

void main() {
  group('StockDetail Widget', () {
    testWidgets('displays stock name', (tester) async {
      final stock = Stock(ticker: 'SBER', name: 'Sberbank');
      
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(home: StockDetailScreen(stock)),
        ),
      );
      
      expect(find.text('Sberbank'), findsOneWidget);
    });
  });
}
```

### Integration Tests

```dart
// integration_test/app_test.dart

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  
  testWidgets('Full user flow', (tester) async {
    await tester.pumpWidget(const App());
    await tester.pumpAndSettle();
    
    // Search for stock
    await tester.enterText(find.byType(SearchField), 'SBER');
    await tester.tap(find.byIcon(Icons.search));
    await tester.pumpAndSettle();
    
    // Open stock detail
    await tester.tap(find.text('SBER'));
    await tester.pumpAndSettle();
    
    // Verify chart is displayed
    expect(find.byType(PriceChart), findsOneWidget);
  });
}
```

---

## Performance Optimization

### Best Practices

1. **Use `const` constructors** where possible
2. **Avoid rebuilding** with `Selector` or `Consumer`
3. **Lazy load** images and heavy widgets
4. **Pagination** for long lists
5. **Cache** API responses locally

### Example: Optimized List

```dart
ListView.builder(
  itemCount: stocks.length,
  itemBuilder: (context, index) {
    return Consumer(
      builder: (context, ref, _) {
        final stock = stocks[index];
        return StockCard(stock: stock);
      },
    );
  },
)
```

---

## Build & Release

### Build Commands

```bash
# iOS
flutter build ios --release

# Android
flutter build apk --release
flutter build appbundle --release

# Windows
flutter build windows --release

# macOS
flutter build macos --release

# Linux
flutter build linux --release
```

### CI/CD

```yaml
# .github/workflows/flutter_build.yml

name: Flutter Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - uses: subosito/flutter-action@v2
        with:
          channel: stable
      
      - run: flutter pub get
      
      - run: flutter analyze
      
      - run: flutter test
      
      - run: flutter build apk --release
```

---

## Version History

| Version | Date       | Changes                    |
|---------|------------|----------------------------|
| 1.0     | 2025-01-XX | Initial frontend spec      |
