import 'dart:async';
import 'package:flutter/material.dart';
import '../utils/theme.dart';
import '../utils/constants.dart';

class MemorySearchBar extends StatefulWidget {
  final String? initialQuery;
  final String? initialSearchType;
  final Function(String query, String searchType) onSearch;
  final VoidCallback? onClear;
  final bool isLoading;

  const MemorySearchBar({
    Key? key,
    this.initialQuery,
    this.initialSearchType,
    required this.onSearch,
    this.onClear,
    this.isLoading = false,
  }) : super(key: key);

  @override
  State<MemorySearchBar> createState() => _MemorySearchBarState();
}

class _MemorySearchBarState extends State<MemorySearchBar> {
  late TextEditingController _searchController;
  late String _selectedSearchType;
  Timer? _debounceTimer;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController(text: widget.initialQuery ?? '');
    _selectedSearchType = widget.initialSearchType ?? 'all';
  }

  @override
  void dispose() {
    _searchController.dispose();
    _debounceTimer?.cancel();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 500), () {
      widget.onSearch(query, _selectedSearchType);
    });
  }

  void _onSearchTypeChanged(String? searchType) {
    if (searchType != null) {
      setState(() {
        _selectedSearchType = searchType;
      });
      widget.onSearch(_searchController.text, searchType);
    }
  }

  void _clearSearch() {
    _searchController.clear();
    widget.onSearch('', _selectedSearchType);
    widget.onClear?.call();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppTheme.spacingM),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        border: const Border(
          bottom: BorderSide(color: AppTheme.borderColor),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search memories and entities...',
                    prefixIcon: widget.isLoading
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: Padding(
                              padding: EdgeInsets.all(12.0),
                              child: CircularProgressIndicator(strokeWidth: 2),
                            ),
                          )
                        : const Icon(Icons.search),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear),
                            onPressed: _clearSearch,
                          )
                        : null,
                    border: const OutlineInputBorder(),
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingM,
                      vertical: AppTheme.spacingS,
                    ),
                  ),
                  onChanged: _onSearchChanged,
                ),
              ),
              const SizedBox(width: AppTheme.spacingM),
              Container(
                width: 120,
                child: DropdownButtonFormField<String>(
                  value: _selectedSearchType,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: AppTheme.spacingS,
                      vertical: AppTheme.spacingS,
                    ),
                  ),
                  items: AppConstants.searchTypes.map((type) {
                    return DropdownMenuItem<String>(
                      value: type,
                      child: Text(
                        AppConstants.searchTypeDisplayNames[type] ?? type,
                        style: const TextStyle(fontSize: 14),
                      ),
                    );
                  }).toList(),
                  onChanged: _onSearchTypeChanged,
                ),
              ),
            ],
          ),
          if (_searchController.text.isNotEmpty) ...[
            const SizedBox(height: AppTheme.spacingS),
            Row(
              children: [
                Icon(
                  Icons.info_outline,
                  size: 16,
                  color: AppTheme.textSecondary,
                ),
                const SizedBox(width: AppTheme.spacingS),
                Text(
                  'Searching in ${AppConstants.searchTypeDisplayNames[_selectedSearchType]?.toLowerCase() ?? _selectedSearchType}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

