# Flutter API Response Parsing Fix

**Date:** 2025-01-15  
**Issue:** Flutter app crashes with `type '_InternalLinkedHashMap' is not a subtype of type 'List'` errors  
**Status:** ✅ Fixed

## Problem Description

The Flutter app was experiencing runtime crashes when loading schedule events and memories. The error occurred because:

1. **Backend API Evolution**: The backend was updated to return standardized wrapped responses:
   ```json
   {
     "success": true,
     "data": {
       "events": [...],
       "pagination": {...}
     },
     "timestamp": "..."
   }
   ```

2. **Flutter App Expectation**: The Flutter app was still expecting legacy array responses:
   ```json
   [...]
   ```

3. **Type Casting Error**: When the app tried to cast `response.data` (a Map) as a List, it caused the runtime error:
   ```
   type '_InternalLinkedHashMap' is not a subtype of type 'List' in type cast
   ```

## Affected Endpoints

- `/api/schedule` - Returns wrapped format with events and pagination
- `/api/memories` - Returns wrapped format with memories and pagination  
- `/api/schedule/users` - Still returns legacy array format
- `/api/schedule/upcoming` - Still returns legacy array format

## Solution Implemented

Updated all Flutter screens to handle both response formats for backward compatibility:

### 1. Schedule Screen (`schedule_screen.dart`)

**Before:**
```dart
final events = (response.data as List)
    .map((json) => ScheduleEvent.fromJson(json))
    .toList();
```

**After:**
```dart
// Handle both new wrapped format and legacy array format
List<dynamic> eventsList;
if (response.data is Map<String, dynamic>) {
  // New wrapped format: {"success": true, "data": {"events": [...], "pagination": {...}}}
  final data = response.data['data'];
  eventsList = data['events'] as List;
} else if (response.data is List) {
  // Legacy format: [...]
  eventsList = response.data as List;
} else {
  throw Exception('Unexpected response format: expected Map or List, got ${response.data.runtimeType}');
}

final events = eventsList
    .map((json) => ScheduleEvent.fromJson(json))
    .toList();
```

### 2. Memories Screen (`memories_screen.dart`)

**Before:**
```dart
final memories = (response.data as List)
    .map((json) => Memory.fromJson(json))
    .toList();
```

**After:**
```dart
// Handle both new wrapped format and legacy array format
List<dynamic> memoriesList;
if (response.data is Map<String, dynamic>) {
  // New wrapped format: {"success": true, "data": {"memories": [...], "pagination": {...}}}
  final data = response.data['data'];
  memoriesList = data['memories'] as List;
} else if (response.data is List) {
  // Legacy format: [...]
  memoriesList = response.data as List;
} else {
  throw Exception('Unexpected response format: expected Map or List, got ${response.data.runtimeType}');
}

final memories = memoriesList
    .map((json) => Memory.fromJson(json))
    .toList();
```

### 3. Dashboard Screen (`dashboard_screen.dart`)

Updated the upcoming events loading to use the same robust pattern for consistency.

## Files Modified

- `mumble_ai_flutter/lib/screens/schedule_screen.dart`
- `mumble_ai_flutter/lib/screens/memories_screen.dart`  
- `mumble_ai_flutter/lib/screens/dashboard_screen.dart`

## Benefits

1. **Backward Compatibility**: App works with both old and new API response formats
2. **Future-Proof**: Can handle additional API format changes
3. **Error Prevention**: Proper type checking prevents runtime crashes
4. **Consistent Pattern**: All screens use the same approach for API response handling

## Testing

- ✅ Schedule screen loads events without crashes
- ✅ Memories screen loads memories without crashes  
- ✅ Dashboard upcoming events work correctly
- ✅ No linting errors introduced
- ✅ APK builds successfully

## Build Output

The fix was tested with a successful APK build:
```
√ Built build\app\outputs\flutter-apk\app-release.apk (19.9MB)
```

## Related Documentation

- [Flutter API Documentation](FLUTTER_API.md)
- [API Design Standards](API.md)
- [Flutter App Integration](FLUTTER_AI_CHAT_INTEGRATION_COMPLETE.md)

## Future Considerations

1. **API Standardization**: Consider updating all backend endpoints to use the wrapped format consistently
2. **Response Validation**: Add response schema validation for additional safety
3. **Error Handling**: Enhance error messages for better debugging
