# Topic: Sign a password-protected PDF with a QR code without ever stripping its password.
# Uses GroupDocs.Signature for Python via .NET: LoadOptions.password opens the encrypted source,
# SaveOptions.use_original_password / SaveOptions.password decide how the signed output is
# protected, and the "Proxy error(...)" RuntimeError contract is how password failures surface.

import os
import sys

import groupdocs.signature as signature
from groupdocs.signature.options import (
    LoadOptions,
    SaveOptions,
    QrCodeSignOptions,
    QrCodeVerifyOptions,
)
from groupdocs.signature.domain import QrCodeTypes
import groupdocs.signature.domain as gsd

DOCS = "documents"
RESULT = "Result"

SOURCE_PDF = os.path.join(DOCS, "protected.pdf")
SIGNED_SAME_PASSWORD_PDF = os.path.join(RESULT, "signed-same-password.pdf")
SIGNED_NEW_PASSWORD_PDF = os.path.join(RESULT, "signed-new-password.pdf")
NOT_WRITTEN_NO_PASSWORD_PDF = os.path.join(RESULT, "not-written-no-password.pdf")
NOT_WRITTEN_WRONG_PASSWORD_PDF = os.path.join(RESULT, "not-written-wrong-password.pdf")

DOCUMENT_PASSWORD = "1234567890"
NEW_DOCUMENT_PASSWORD = "NewPassw0rd2026"
WRONG_PASSWORD = "not-the-password"
QR_TEXT = "GroupDocs.Signature demo - approved"


def apply_license() -> None:
    # Point this at your .lic file to remove evaluation limits.
    # Get a free temporary licence: https://purchase.groupdocs.com/temporary-license
    license_path = "REPLACE_WITH_YOUR_LICENSE_PATH"
    if os.path.exists(license_path):
        signature.License().set_license(license_path)
        print("[license] applied")
    else:
        print("[license] no licence set - running in evaluation mode")


def proxy_error_name(error: RuntimeError) -> str:
    """
    Extracts the .NET exception name that GroupDocs wrapped inside a Python RuntimeError.

    Remarks:
        The Python binding exposes PasswordRequiredException, IncorrectPasswordException and
        GroupDocsSignatureException as bare names that do not inherit from BaseException, so putting
        them in an except clause raises TypeError instead of catching anything. Every failure arrives
        as a RuntimeError whose message begins with "Proxy error(<Name>): ". This helper returns that
        <Name> so callers can branch on the original cause, or an empty string when the message
        carries no such prefix.
    """
    message = str(error)
    marker = "Proxy error("
    if not message.startswith(marker):
        return ""
    start = len(marker)
    end = message.find(")", start)
    if end < 0:
        return ""
    return message[start:end]


def inspect_protected_document(source_path: str, password: str) -> tuple:
    """
    Reads format, page count and size from an encrypted PDF without removing its protection.

    Remarks:
        Opens the document through LoadOptions.password and calls get_document_info. The file on disk
        stays encrypted and nothing is decrypted to a temporary copy, which is what lets a pipeline
        inspect a protected document it is not allowed to store in the clear. Returns a
        (file_format, page_count, size_in_bytes) tuple.
    """
    load_options = LoadOptions()
    load_options.password = password
    with signature.Signature(source_path, load_options) as sign:
        info = sign.get_document_info()
        return info.file_type.file_format, info.page_count, info.size


def sign_without_password(source_path: str, output_path: str, qr_text: str) -> str:
    """
    Shows what an encrypted PDF does when it is opened with no password at all.

    Remarks:
        Builds Signature without LoadOptions, so the source cannot be opened and the sign call fails
        before anything is written. GroupDocs reports this as a RuntimeError carrying
        "Proxy error(PasswordRequiredException)". Returns the wrapped exception name, or an empty
        string if the document unexpectedly signed.
    """
    options = _build_qr_options(qr_text)
    try:
        with signature.Signature(source_path) as sign:
            sign.sign(output_path, options)
        return ""
    except RuntimeError as error:
        return proxy_error_name(error)


def sign_with_wrong_password(source_path: str, output_path: str, wrong_password: str, qr_text: str) -> str:
    """
    Shows how a wrong password is reported, as distinct from a missing one.

    Remarks:
        Supplies an incorrect LoadOptions.password, which GroupDocs rejects with
        "Proxy error(IncorrectPasswordException)" rather than the PasswordRequiredException raised
        when no password is given at all. Telling the two apart is what lets a caller decide between
        prompting for a password and reporting a bad one. Returns the wrapped exception name, or an
        empty string if the document unexpectedly signed.
    """
    load_options = LoadOptions()
    load_options.password = wrong_password
    options = _build_qr_options(qr_text)
    try:
        with signature.Signature(source_path, load_options) as sign:
            sign.sign(output_path, options)
        return ""
    except RuntimeError as error:
        return proxy_error_name(error)


def sign_keeping_original_password(source_path: str, output_path: str, password: str, qr_text: str) -> int:
    """
    Signs an encrypted PDF with a QR code and leaves the output protected by the same password.

    Remarks:
        Passes the password through LoadOptions and calls sign without SaveOptions.
        SaveOptions.use_original_password defaults to True, so GroupDocs re-applies the source
        password to the signed output: the document is never written to disk unprotected, not even
        briefly, and no decrypt-sign-reencrypt dance is needed. Returns the number of signatures
        written.
    """
    load_options = LoadOptions()
    load_options.password = password
    options = _build_qr_options(qr_text)
    with signature.Signature(source_path, load_options) as sign:
        result = sign.sign(output_path, options)
        return len(result.succeeded)


def sign_with_new_password(source_path: str, output_path: str, password: str, new_password: str, qr_text: str) -> int:
    """
    Signs an encrypted PDF and re-keys the signed copy to a different password.

    Remarks:
        Opens the source with its current password through LoadOptions, then passes SaveOptions with
        use_original_password set to False and password set to the replacement. This is the rotation
        path: the signed copy opens only with the new password while the source file keeps the old
        one. Returns the number of signatures written.
    """
    load_options = LoadOptions()
    load_options.password = password
    save_options = SaveOptions()
    save_options.password = new_password
    save_options.use_original_password = False
    options = _build_qr_options(qr_text)
    with signature.Signature(source_path, load_options) as sign:
        result = sign.sign(output_path, options, save_options)
        return len(result.succeeded)


def verify_signed_protected_document(signed_path: str, password: str, expected_text: str) -> int:
    """
    Re-opens a signed, still-encrypted PDF and reads its QR-code signature back.

    Remarks:
        Supplying the password through LoadOptions is itself the proof that the output stayed
        protected, and QrCodeVerifyOptions with TextMatchType.CONTAINS proves the signature survived
        the save. A zero count means the read-back failed, most often an unlicensed build or a licence
        that does not cover GroupDocs.Signature. Returns the count of matching QR-code signatures.
    """
    load_options = LoadOptions()
    load_options.password = password
    with signature.Signature(signed_path, load_options) as sign:
        options = QrCodeVerifyOptions()
        options.text = expected_text
        options.match_type = gsd.TextMatchType.CONTAINS
        options.all_pages = True
        result = sign.verify(options)
        return len(result.succeeded)


def _build_qr_options(qr_text: str) -> QrCodeSignOptions:
    """
    Builds the QR-code signing options shared by every signing path in this sample.

    Remarks:
        Keeps one definition of the signature's text, encoding and placement so the four signing
        methods differ only in how they handle the password. Properties are snake_case on the Python
        binding and the encode type is an uppercase enum member, QrCodeTypes.QR.
    """
    options = QrCodeSignOptions()
    options.text = qr_text
    options.encode_type = QrCodeTypes.QR
    options.left = 50
    options.top = 50
    options.width = 120
    options.height = 120
    return options


def main() -> int:
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(RESULT, exist_ok=True)
    apply_license()

    if not os.path.exists(SOURCE_PDF):
        print("Missing source document: " + os.path.abspath(SOURCE_PDF), file=sys.stderr)
        return 1

    file_format, page_count, size = inspect_protected_document(SOURCE_PDF, DOCUMENT_PASSWORD)
    print("Protected source: " + file_format)
    print("  pages: " + str(page_count) + ", size: " + str(size) + " bytes")

    missing = sign_without_password(SOURCE_PDF, NOT_WRITTEN_NO_PASSWORD_PDF, QR_TEXT)
    print("No password       -> " + (missing or "signed (unexpected)"))

    incorrect = sign_with_wrong_password(SOURCE_PDF, NOT_WRITTEN_WRONG_PASSWORD_PDF, WRONG_PASSWORD, QR_TEXT)
    print("Wrong password    -> " + (incorrect or "signed (unexpected)"))

    kept = sign_keeping_original_password(SOURCE_PDF, SIGNED_SAME_PASSWORD_PDF, DOCUMENT_PASSWORD, QR_TEXT)
    print("Same password     -> " + str(kept) + " signature(s): " + os.path.abspath(SIGNED_SAME_PASSWORD_PDF))

    rekeyed = sign_with_new_password(
        SOURCE_PDF, SIGNED_NEW_PASSWORD_PDF, DOCUMENT_PASSWORD, NEW_DOCUMENT_PASSWORD, QR_TEXT
    )
    print("New password      -> " + str(rekeyed) + " signature(s): " + os.path.abspath(SIGNED_NEW_PASSWORD_PDF))

    verified = verify_signed_protected_document(SIGNED_SAME_PASSWORD_PDF, DOCUMENT_PASSWORD, QR_TEXT)
    print("Verified QR codes -> " + str(verified) + " (read back through the original password)")

    return 0 if verified > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
