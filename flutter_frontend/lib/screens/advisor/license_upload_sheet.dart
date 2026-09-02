import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_frontend/models/auth_models.dart';
import 'package:flutter_frontend/repositories/auth_repository.dart';
import 'package:flutter_frontend/theme/app_theme.dart';

const _maxDocumentBytes = 10 * 1024 * 1024;
const _allowedExtensions = {'pdf', 'jpg', 'jpeg', 'png'};

class LicenseDocument {
  const LicenseDocument({
    required this.name,
    required this.bytes,
    required this.contentType,
  });

  final String name;
  final Uint8List bytes;
  final String contentType;
}

typedef LicenseDocumentPicker = Future<LicenseDocument?> Function();

Future<void> showLicenseUploadSheet({
  required BuildContext context,
  required AuthRepository repository,
  required ValueChanged<AdvisorLicense> onSubmitted,
  LicenseDocumentPicker? documentPicker,
  AdvisorLicense? rejectedLicense,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    showDragHandle: true,
    builder: (_) => FractionallySizedBox(
      heightFactor: 0.88,
      child: LicenseUploadSheet(
        repository: repository,
        onSubmitted: onSubmitted,
        documentPicker: documentPicker,
        rejectedLicense: rejectedLicense,
      ),
    ),
  );
}

class LicenseUploadSheet extends StatefulWidget {
  const LicenseUploadSheet({
    super.key,
    required this.repository,
    required this.onSubmitted,
    this.documentPicker,
    this.rejectedLicense,
  });

  final AuthRepository repository;
  final ValueChanged<AdvisorLicense> onSubmitted;
  final LicenseDocumentPicker? documentPicker;
  final AdvisorLicense? rejectedLicense;

  @override
  State<LicenseUploadSheet> createState() => _LicenseUploadSheetState();
}

class _LicenseUploadSheetState extends State<LicenseUploadSheet> {
  final _stateController = TextEditingController();
  final _numberController = TextEditingController();
  final _typeController = TextEditingController();
  LicenseDocument? _document;
  bool _picking = false;
  bool _submitting = false;
  String? _error;
  String? _success;

  bool get _isResubmission => widget.rejectedLicense != null;

  @override
  void initState() {
    super.initState();
    final rejected = widget.rejectedLicense;
    if (rejected != null) {
      _stateController.text = rejected.state;
      _numberController.text = rejected.licenseNumber;
      _typeController.text = rejected.licenseType ?? '';
    }
  }

  @override
  void dispose() {
    _stateController.dispose();
    _numberController.dispose();
    _typeController.dispose();
    super.dispose();
  }

  Future<LicenseDocument?> _pickWithPlatform() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: _allowedExtensions.toList(),
      allowMultiple: false,
      withData: true,
    );
    if (result == null) return null;
    final file = result.files.single;
    final bytes = file.bytes;
    if (bytes == null) {
      throw StateError('Unable to read the selected document.');
    }
    return LicenseDocument(
      name: file.name,
      bytes: bytes,
      contentType: _contentTypeFor(file.extension),
    );
  }

  Future<void> _pickDocument() async {
    if (_picking || _submitting) return;
    setState(() {
      _picking = true;
      _error = null;
      _success = null;
    });
    try {
      final document = await (widget.documentPicker ?? _pickWithPlatform)();
      if (!mounted || document == null) return;
      final validationError = _validateDocument(document);
      if (validationError != null) {
        setState(() => _error = validationError);
        return;
      }
      setState(() => _document = document);
    } on PlatformException catch (error) {
      if (!mounted || _isPickerCancellation(error)) return;
      setState(() {
        _error = 'The document picker could not be opened. Please try again.';
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = 'The selected document could not be read. Please try again.';
        });
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _submit() async {
    final state = _stateController.text.trim().toUpperCase();
    final number = _numberController.text.trim();
    final document = _document;
    if (!RegExp(r'^[A-Z]{2}$').hasMatch(state)) {
      setState(() => _error = 'Enter a valid two-letter state code.');
      return;
    }
    if (number.isEmpty) {
      setState(() => _error = 'License number is required.');
      return;
    }
    if (document == null) {
      setState(() => _error = 'Please select a license document.');
      return;
    }
    final validationError = _validateDocument(document);
    if (validationError != null) {
      setState(() => _error = validationError);
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
      _success = null;
    });
    try {
      final license = _isResubmission
          ? await widget.repository.resubmitLicense(
              licenseId: widget.rejectedLicense!.id,
              licenseType: _typeController.text,
              filename: document.name,
              documentBytes: document.bytes,
              contentType: document.contentType,
            )
          : await widget.repository.submitLicense(
              state: state,
              licenseNumber: number,
              licenseType: _typeController.text,
              filename: document.name,
              documentBytes: document.bytes,
              contentType: document.contentType,
            );
      if (!mounted) return;
      try {
        widget.onSubmitted(license);
      } catch (_) {
        // The upload has succeeded. A parent refresh must not turn that into
        // an unhandled upload failure if its screen is closing concurrently.
      }
      if (!mounted) return;
      setState(() {
        _success = _isResubmission
            ? 'License resubmitted for review.'
            : 'License submitted for review.';
        _stateController.clear();
        _numberController.clear();
        _typeController.clear();
        _document = null;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: EdgeInsets.fromLTRB(
        20,
        4,
        20,
        24 + MediaQuery.viewInsetsOf(context).bottom,
      ),
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _isResubmission ? 'Resubmit License' : 'Upload License',
                    style: TextStyle(
                      color: context.appInk,
                      fontSize: 24,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    _isResubmission
                        ? 'Replace the rejected document for a new review.'
                        : 'Submit a state license for verification.',
                    style: TextStyle(color: context.appMuted),
                  ),
                ],
              ),
            ),
            IconButton(
              onPressed: () => Navigator.of(context).pop(),
              tooltip: 'Close license upload',
              icon: const Icon(Icons.close),
            ),
          ],
        ),
        const SizedBox(height: 20),
        TextField(
          controller: _stateController,
          enabled: !_submitting && !_isResubmission,
          textCapitalization: TextCapitalization.characters,
          maxLength: 2,
          inputFormatters: [
            FilteringTextInputFormatter.allow(RegExp('[A-Za-z]')),
            UpperCaseTextFormatter(),
          ],
          decoration: const InputDecoration(
            labelText: 'State code',
            hintText: 'TX',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _numberController,
          enabled: !_submitting && !_isResubmission,
          maxLength: 80,
          decoration: const InputDecoration(
            labelText: 'License number',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 10),
        TextField(
          controller: _typeController,
          enabled: !_submitting,
          maxLength: 80,
          decoration: const InputDecoration(
            labelText: 'License type (optional)',
            border: OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 10),
        OutlinedButton.icon(
          onPressed: _picking || _submitting ? null : _pickDocument,
          icon: const Icon(Icons.upload_file),
          label: Text(
            _picking
                ? 'Opening files…'
                : _document?.name ?? 'Select PDF or image',
          ),
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(52),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          'PDF, JPG, JPEG, or PNG · maximum 10 MB',
          style: TextStyle(color: context.appMuted, fontSize: 12),
        ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Text(_error!, style: const TextStyle(color: Color(0xFFB91C1C))),
        ],
        if (_success != null) ...[
          const SizedBox(height: 12),
          Text(
            _success!,
            style: const TextStyle(
              color: Color(0xFF15803D),
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
        const SizedBox(height: 18),
        SizedBox(
          height: 50,
          child: FilledButton.icon(
            onPressed: _submitting ? null : _submit,
            icon: _submitting
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.verified_user_outlined),
            label: Text(
              _submitting
                  ? 'Submitting…'
                  : _isResubmission
                  ? 'Resubmit License'
                  : 'Submit License',
            ),
          ),
        ),
      ],
    );
  }
}

class UpperCaseTextFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    return newValue.copyWith(text: newValue.text.toUpperCase());
  }
}

String? _validateDocument(LicenseDocument document) {
  if (document.bytes.isEmpty) {
    return 'The selected document is empty. Choose another file.';
  }
  final extension = document.name.toLowerCase().split('.').last;
  if (!_allowedExtensions.contains(extension)) {
    return 'Document must be a PDF, JPG, JPEG, or PNG file.';
  }
  if (document.bytes.length > _maxDocumentBytes) {
    return 'Document must be 10 MB or smaller.';
  }
  return null;
}

bool _isPickerCancellation(PlatformException error) {
  final value = '${error.code} ${error.message ?? ''}'.toLowerCase();
  return value.contains('cancel') || value.contains('abort');
}

String _contentTypeFor(String? extension) {
  switch (extension?.toLowerCase()) {
    case 'pdf':
      return 'application/pdf';
    case 'png':
      return 'image/png';
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg';
    default:
      return 'application/octet-stream';
  }
}
