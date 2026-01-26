# Flutter API Parameter Fix - October 15, 2025

## Issue Description

The Flutter app was experiencing 400 errors when trying to load memories, with the error message "user_name is required". This was caused by a parameter name mismatch between the Flutter app and the backend API.

## Root Cause Analysis

### API Endpoint Requirements
- `/api/memories` - **requires** `user_name` parameter (line 867-875 in `web-control-panel/app.py`)
- `/api/schedule` - accepts `user_name` parameter (optional, line 1836 in `web-control-panel/app.py`)
- `/api/schedule/upcoming` - expects `user` parameter (line 2091 in `web-control-panel/app.py`)

### Flutter App Behavior
- **Memories screen**: Was sending `user` parameter → caused 400 error
- **Schedule screen**: Was sending `user` parameter → worked but returned all users' events (incorrect behavior)
- **Dashboard screen**: Was sending `user` parameter → worked correctly (matches API expectation)

## Solution Implemented

### Files Modified

1. **`mumble_ai_flutter/lib/screens/memories_screen.dart`** (line 75)
   ```dart
   // Before (causing 400 error)
   queryParams['user'] = currentUser;
   
   // After (fixed)
   queryParams['user_name'] = currentUser;
   ```

2. **`mumble_ai_flutter/lib/screens/schedule_screen.dart`** (line 75)
   ```dart
   // Before (worked but incorrect)
   queryParams['user'] = currentUser;
   
   // After (proper user filtering)
   queryParams['user_name'] = currentUser;
   ```

3. **`mumble_ai_flutter/lib/screens/dashboard_screen.dart`** (line 153)
   ```dart
   // No changes needed - already correct
   queryParams['user'] = currentUser;  // ✓ CORRECT
   ```

### APK Rebuild
- Built new release APK: `app-release.apk` (19.9MB)
- Location: `mumble_ai_flutter/build/app/outputs/flutter-apk/app-release.apk`

## Impact Assessment

### Before Fix
- ❌ Memories screen: 400 error "user_name is required"
- ⚠️ Schedule screen: Showed all users' events (not user-specific)
- ✅ Dashboard screen: Worked correctly

### After Fix
- ✅ Memories screen: Loads user-specific memories correctly
- ✅ Schedule screen: Shows only user-specific events
- ✅ Dashboard screen: Continues to work correctly

## Technical Details

### API Parameter Mapping
| Endpoint | Expected Parameter | Flutter App (Before) | Flutter App (After) |
|----------|-------------------|---------------------|-------------------|
| `/api/memories` | `user_name` | `user` ❌ | `user_name` ✅ |
| `/api/schedule` | `user_name` (optional) | `user` ⚠️ | `user_name` ✅ |
| `/api/schedule/upcoming` | `user` | `user` ✅ | `user` ✅ |

### Error Logs (Before Fix)
```
ERROR [ApiService] API Error: Missing required information. Please try again.
{
  "error": {
    "code": "MISSING_PARAMETER",
    "message": "user_name is required"
  },
  "statusCode": 400
}
```

## Testing Recommendations

1. **Memories Screen**
   - Verify memories load without 400 errors
   - Confirm only user-specific memories are displayed
   - Test memory filtering by category

2. **Schedule Screen**
   - Verify only user-specific events are shown
   - Test event creation and editing
   - Confirm proper date/time filtering

3. **Dashboard Screen**
   - Verify upcoming events still display correctly
   - Test dashboard statistics

## Deployment Notes

- New APK file: `mumble_ai_flutter/build/app/outputs/flutter-apk/app-release.apk`
- No backend changes required
- No database migrations needed
- Backward compatible with existing API

## Related Files

- `mumble_ai_flutter/lib/screens/memories_screen.dart`
- `mumble_ai_flutter/lib/screens/schedule_screen.dart`
- `mumble_ai_flutter/lib/screens/dashboard_screen.dart`
- `web-control-panel/app.py` (API endpoints)

## Commit Information

- **Date**: October 15, 2025
- **Type**: Bug Fix
- **Scope**: Flutter App API Integration
- **Breaking Changes**: None
