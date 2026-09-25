# Signing Password-Protected PDFs in Python

[![Product Page](https://img.shields.io/badge/Product%20Page-2865E0?style=for-the-badge&logo=appveyor&logoColor=white)](https://github.com/groupdocs-signature/GroupDocs.Signature-Docs)
[![Docs](https://img.shields.io/badge/Docs-2865E0?style=for-the-badge&logo=Hugo&logoColor=white)](https://docs.groupdocs.com/signature/python-net/)
[![Blog](https://img.shields.io/badge/Blog-2865E0?style=for-the-badge&logo=WordPress&logoColor=white)](https://blog.groupdocs.com/categories/groupdocs.signature-product-family/)
[![Free Support](https://img.shields.io/badge/Free%20Support-2865E0?style=for-the-badge&logo=Discourse&logoColor=white)](https://forum.groupdocs.com/c/signature/13)
[![Temporary License](https://img.shields.io/badge/Temporary%20License-2865E0?style=for-the-badge&logo=rocket&logoColor=white)](https://purchase.groupdocs.com/temp-license/100124)

## Overview

`qr-sign-password-protected-pdf-python` is a runnable Python script that applies a QR-code signature to an encrypted PDF and writes the result still encrypted. The source password goes in through `LoadOptions`, the output protection is decided by `SaveOptions`, and at no point does an unprotected copy touch the disk.

The script covers four password paths in one run: no password supplied, the wrong password, the correct password with the protection preserved, and the correct password with the signed copy re-keyed to a new one. It then reopens the signed file through its password and reads the QR code back.

## Technology Stack

Python 3 with `groupdocs-signature-net==26.1`, the Python via .NET binding. The sample needs no other dependency: the input is a PDF encrypted with a user password, and the output goes to `Result/`.

## Problem Statement

The obvious way to sign an encrypted document is the wrong one. Decrypt it, sign the plaintext, re-encrypt the result - and for the duration of those three steps a readable copy of a document that was deliberately protected exists on disk, inside whatever temp directory the process happened to use. In a regulated pipeline that window is the finding, not the signature.

The second problem is error handling, and it is specific to this binding. `PasswordRequiredException`, `IncorrectPasswordException` and `GroupDocsSignatureException` are exposed as bare names that do not inherit from `BaseException`. Putting one in an `except` clause raises `TypeError: catching classes that do not inherit from BaseException is not allowed` - so the obvious code does not merely fail to catch the error, it replaces it with a different one.

## Solution Overview

Every failure from the binding arrives as a `RuntimeError` whose message starts with `Proxy error(<Name>): `. Parsing that prefix gives back the original cause, which is what lets a caller distinguish "this document needs a password" from "that password is wrong" - a distinction worth having, because one means prompt the user and the other means the credential is stale.

Signing itself never decrypts. `LoadOptions.password` opens the source in place, and `SaveOptions.use_original_password` (default `True`) re-applies the same password to the output. Setting it to `False` alongside `SaveOptions.password` rotates the signed copy to a new credential while the source keeps its old one.

## Prerequisites

- **Python 3** with `pip install -r requirements.txt`
- **groupdocs-signature-net 26.1** - pinned in `requirements.txt`
- **A password-protected PDF** - `documents/protected.pdf` ships with the sample, opened with `1234567890`
- **Licence (optional)** - point `license_path` at your `.lic`; without one the run is in evaluation mode, and the QR read-back may return zero

## Getting Started

### Installation

**Using Package Manager:**

```bash
pip install -r requirements.txt
```

**Manual Installation:**

```bash
pip install groupdocs-signature-net==26.1
```

### Configuration

Nothing needs configuring for a first run. `python sign_protected_document_demo.py` prints the source document info, the two failure names, the two signed outputs and the verification count. To sign your own file, replace `documents/protected.pdf` and set `DOCUMENT_PASSWORD` to its password.

## Repository Structure

```
qr-sign-password-protected-pdf-python/
│
├── sign_protected_document_demo.py
├── requirements.txt
├── documents/
│   └── protected.pdf
└── Result/
    ├── signed-same-password.pdf
    └── signed-new-password.pdf
```

### File Descriptions

- **sign_protected_document_demo.py** - the whole sample: inspection, both failure paths, both signing paths, verification
- **requirements.txt** - pins `groupdocs-signature-net==26.1`
- **documents/protected.pdf** - the encrypted input, password `1234567890`
- **Result/** - the two signed copies a full run produces, one per password strategy

## Code Implementation

### Implementation: Reads format, page count and size from an encrypted PDF without removing its protection

Run this before deciding anything else. It answers whether the password you hold actually opens the document, and how many pages you are about to sign, without producing a decrypted artifact anywhere.

```python
load_options = LoadOptions()
load_options.password = password
with signature.Signature(source_path, load_options) as sign:
    info = sign.get_document_info()
    return info.file_type.file_format, info.page_count, info.size
```

Key components: `LoadOptions.password`, `Signature.get_document_info`.

Output: a `(file_format, page_count, size_in_bytes)` tuple - on the shipped sample, PDF with its page count and byte size.

The file on disk stays encrypted throughout, which is the point: a pipeline that is not allowed to store the plaintext can still report on the document.

### Implementation: Extracts the .NET exception name that GroupDocs wrapped inside a Python RuntimeError

This is the supporting helper the two failure paths depend on, and the reason they can tell their failures apart at all.

```python
message = str(error)
marker = "Proxy error("
if not message.startswith(marker):
    return ""
start = len(marker)
end = message.find(")", start)
if end < 0:
    return ""
return message[start:end]
```

Key components: the `Proxy error(<Name>): ` prefix contract.

Output: the wrapped exception name, for example `PasswordRequiredException`, or an empty string when the message has no such prefix.

I wrote that `except IncorrectPasswordException:` first, like everyone does, and spent the next twenty minutes reading a `TypeError` that had nothing to do with passwords. Do not try to catch the named exception types directly. They are bare names on this binding and do not inherit from `BaseException`, so an `except` clause naming one raises `TypeError` instead of catching anything.

### Implementation: Shows what an encrypted PDF does when it is opened with no password at all

The first failure path, run deliberately so the message is visible next to the working code.

```python
options = _build_qr_options(qr_text)
try:
    with signature.Signature(source_path) as sign:
        sign.sign(output_path, options)
    return ""
except RuntimeError as error:
    return proxy_error_name(error)
```

Key components: `Signature` constructed without `LoadOptions`.

Output: `PasswordRequiredException`. Nothing is written - the failure happens on open, before any signing work starts.

### Implementation: Shows how a wrong password is reported, as distinct from a missing one

Same shape, different cause, and the distinction is the whole reason this method exists separately.

```python
load_options = LoadOptions()
load_options.password = wrong_password
options = _build_qr_options(qr_text)
try:
    with signature.Signature(source_path, load_options) as sign:
        sign.sign(output_path, options)
    return ""
except RuntimeError as error:
    return proxy_error_name(error)
```

Key components: `LoadOptions.password` holding an incorrect value.

Output: `IncorrectPasswordException`, not `PasswordRequiredException`.

A caller that branches on these two names can prompt for a password in one case and report a stale credential in the other. A caller that only sees `RuntimeError` cannot.

### Implementation: Signs an encrypted PDF with a QR code and leaves the output protected by the same password

The default path, and the one most pipelines want.

```python
load_options = LoadOptions()
load_options.password = password
options = _build_qr_options(qr_text)
with signature.Signature(source_path, load_options) as sign:
    result = sign.sign(output_path, options)
    return len(result.succeeded)
```

Key components: `LoadOptions.password` in, no `SaveOptions` at all.

Output: the number of signatures written, and `Result/signed-same-password.pdf` encrypted with the original password.

There is no `SaveOptions` here on purpose: `use_original_password` defaults to `True`, so GroupDocs re-applies the source password to the output. The document is never written unprotected, not even briefly.

### Implementation: Signs an encrypted PDF and re-keys the signed copy to a different password

The rotation path. The source keeps its current password; the signed copy gets a new one.

```python
load_options = LoadOptions()
load_options.password = password
save_options = SaveOptions()
save_options.password = new_password
save_options.use_original_password = False
options = _build_qr_options(qr_text)
with signature.Signature(source_path, load_options) as sign:
    result = sign.sign(output_path, options, save_options)
    return len(result.succeeded)
```

Key components: `SaveOptions.use_original_password = False` plus `SaveOptions.password`.

Output: `Result/signed-new-password.pdf`, which opens only with the replacement password.

Setting `password` without clearing `use_original_password` does nothing useful - the flag wins, and the output keeps the old credential.

### Implementation: Re-opens a signed, still-encrypted PDF and reads its QR-code signature back

Verification doubles as proof that the output stayed protected, because it has to supply the password to get in.

```python
load_options = LoadOptions()
load_options.password = password
with signature.Signature(signed_path, load_options) as sign:
    options = QrCodeVerifyOptions()
    options.text = expected_text
    options.match_type = gsd.TextMatchType.CONTAINS
    options.all_pages = True
    result = sign.verify(options)
    return len(result.succeeded)
```

Key components: `QrCodeVerifyOptions` with `CONTAINS` matching across all pages.

Output: the count of matching QR-code signatures - above zero means the signature survived the save.

A zero here usually means an unlicensed build, or a licence that does not cover GroupDocs.Signature, rather than a signing failure.

### Why does the sample define the QR options in one place?

Because the four signing paths differ only in how they handle the password, and sharing `_build_qr_options` makes that visible. The helper sets the text, `QrCodeTypes.QR` as the encode type, and a 120x120 box at (50, 50). Two details are easy to get wrong on this binding: the properties are snake_case, and the encode type is an uppercase enum member.

## Best Practices

Keep `use_original_password` alone unless you are deliberately rotating; the default is the safe one and it needs no code. Branch on the parsed proxy name rather than on message text, since the text carries paths and varies. Inspect before signing when the password came from a user, so a bad credential fails on a cheap call instead of halfway through a batch. And treat a zero verification count as a licensing question first: the signing call would have raised if it had actually failed.

## Additional Resources

- [**Step-by-step use case guide in the documentation**](https://docs.groupdocs.com/signature/python-net/use-cases/sign-password-protected-pdf/) - the four password paths with the decision table
- [**In-depth blog article about this project**](https://blog.groupdocs.com/signature/sign-password-protected-pdf-python-net/) - why the decrypt-sign-reencrypt habit is worth dropping
- [**eSign Document with QR Code Signature**](https://docs.groupdocs.com/signature/python-net/esign-document-with-qr-code-signature/) - the QR signing reference behind `QrCodeSignOptions`
- [**How to Search for QR Code Signatures**](https://docs.groupdocs.com/signature/python-net/search-for-qr-code-e-signatures/) - the read-back side of the same API
- [**GroupDocs.Signature for Python via .NET documentation**](https://docs.groupdocs.com/signature/python-net/) - getting started and advanced topics

## Keywords

`sign password protected pdf`, `qr code signature`, `python signing`, `encrypted pdf`, `load options password`, `save options`, `password rotation`, `groupdocs signature`, `python via net`, `pdf security`, `LoadOptions`, `SaveOptions`, `use_original_password`, `QrCodeSignOptions`, `QrCodeVerifyOptions`, `PasswordRequiredException`, `IncorrectPasswordException`, `proxy error`, `document signing`, `pdf encryption`, `re-key pdf password`, `evaluation mode`

## Support

[Free Support Forum](https://forum.groupdocs.com/c/signature/13) | [Temporary License](https://purchase.groupdocs.com/temp-license/100124) | [API Reference](https://reference.groupdocs.com/signature/python-net/)
