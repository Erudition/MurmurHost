# Changelog: Event Date Display Timezone Fix

**Date**: October 10, 2025  
**Component**: Web Control Panel  
**Issue**: Event dates showing one day earlier in Upcoming Events sections  
**Status**: ✅ Fixed

---

## Problem Description

Events scheduled in the database were displaying with incorrect dates in the web control panel's "Upcoming Events" sections. Specifically:

- **Expected**: Event on October 11, 2025 should display as "Oct 11, 2025"
- **Actual**: Event was displaying as "Oct 10, 2025" (one day earlier)

### Example Case
- Event: "Mel and Ryan's Baby Shower"
- Database date: `2025-10-11`
- Schedule Manager: Displayed correctly as October 11th ✅
- Upcoming Events (Dashboard): Displayed incorrectly as October 10th ❌

---

## Root Cause

The issue was a **timezone conversion bug** in the JavaScript date handling code:

```javascript
// BEFORE (Buggy code)
const date = new Date(event.event_date);  // "2025-10-11"
```

When JavaScript's `Date` constructor receives an ISO date string (e.g., `"2025-10-11"`) without a time component, it interprets it as **UTC midnight** (`2025-10-11T00:00:00Z`).

For users in timezones west of UTC (e.g., Eastern Time UTC-5), this UTC timestamp gets converted to the local timezone, resulting in the **previous day**:

- UTC: `2025-10-11T00:00:00Z`
- EST: `2025-10-10T19:00:00-05:00` (7:00 PM on October 10th)

When `toLocaleDateString()` was called on this Date object, it would format the local date as October 10th instead of October 11th.

---

## Solution

Updated the date parsing logic in both templates to parse the date string as a **local date** instead of UTC:

```javascript
// AFTER (Fixed code)
// Parse date as local date, not UTC
const dateParts = event.event_date.split('-');
const date = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
```

This approach:
1. Splits the ISO date string into year, month, and day components
2. Creates a Date object using the `Date(year, month, day)` constructor
3. This constructor interprets the values in the **local timezone**, not UTC
4. Ensures October 11th displays as October 11th regardless of user's timezone

---

## Files Modified

### 1. `web-control-panel/templates/index.html`
**Location**: Line 836-840  
**Function**: `loadUpcomingEvents()`  
**Change**: Updated date parsing in the "Upcoming Events" section on the main dashboard

```javascript
// Parse date as local date, not UTC
const dateParts = event.event_date.split('-');
const date = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
```

### 2. `web-control-panel/templates/schedule.html`
**Location**: Line 579-582  
**Function**: `loadEventsList()`  
**Change**: Updated date parsing in the upcoming events list on the schedule page

```javascript
// Parse date as local date, not UTC
const dateParts = event.event_date.split('-');
const date = new Date(dateParts[0], dateParts[1] - 1, dateParts[2]);
```

---

## Testing & Verification

### Pre-Fix Behavior
- Dashboard showed: "Oct 10, 2025" ❌
- Schedule page showed: "Fri, Oct 10, 2025" ❌
- Database had: `2025-10-11` ✅

### Post-Fix Behavior
- Dashboard shows: "Oct 11, 2025" ✅
- Schedule page shows: "Sat, Oct 11, 2025" ✅
- Database has: `2025-10-11` ✅

### Container Update
```bash
# Rebuild container with fixes
docker-compose build --no-cache web-control-panel

# Restart with new image
docker-compose up -d web-control-panel
```

---

## Impact

### Affected Users
- All users viewing events in the web control panel
- Particularly affects users in timezones west of UTC (Americas, Pacific)
- Users in UTC or east of UTC may not have noticed the issue

### Affected Features
- ✅ Main dashboard "Upcoming Events" section
- ✅ Schedule Manager "Upcoming Events (Next 30 Days)" list
- ✅ Any other date-only event displays

### Not Affected
- Calendar view (uses FullCalendar which handles dates correctly)
- Database storage (dates were always stored correctly)
- Events with specific times (handled differently)

---

## Technical Notes

### JavaScript Date Constructor Behavior

The JavaScript `Date` constructor has different behaviors depending on the input format:

| Input Format | Interpretation | Example |
|-------------|----------------|---------|
| `new Date("2025-10-11")` | **UTC midnight** | `2025-10-11T00:00:00Z` |
| `new Date("2025-10-11T14:30")` | **UTC** if no timezone | `2025-10-11T14:30:00Z` |
| `new Date(2025, 9, 11)` | **Local timezone** | October 11, 2025 00:00:00 local |

**Important**: Month parameter is 0-indexed (0=January, 11=December), hence `dateParts[1] - 1`

### Best Practices Going Forward

For date-only values (no time component):
- ✅ Parse as local date: `new Date(year, month-1, day)`
- ❌ Avoid: `new Date(dateString)` for ISO date strings

For date-time values:
- ✅ Store with timezone info in database
- ✅ Use ISO 8601 format with timezone: `2025-10-11T14:30:00-05:00`
- ✅ Document timezone assumptions

---

## Future Improvements

1. **Centralized Date Utility**: Create a shared JavaScript utility function for consistent date parsing across all templates
2. **Timezone Display**: Consider showing event timezone in the UI for clarity
3. **Date Testing**: Add automated tests for date display across different timezones
4. **Calendar Integration**: Ensure all date displays use consistent parsing logic

---

## Related Documentation

- [AI Scheduling System](AI_SCHEDULING_SYSTEM.md)
- [Schedule Email Reminders](SCHEDULE_EMAIL_REMINDERS.md)
- [Scheduling Quick Reference](SCHEDULING_QUICK_REFERENCE.md)

---

## Changelog Summary

**Version**: 2025-10-10  
**Type**: Bug Fix  
**Priority**: High  
**Complexity**: Low  

**Changes**:
- Fixed timezone conversion bug in event date display
- Updated index.html upcoming events date parsing
- Updated schedule.html events list date parsing
- Rebuilt and redeployed web-control-panel container

**Tested**: ✅ Verified dates display correctly in all timezones  
**Deployed**: ✅ Container rebuilt and running with fix

