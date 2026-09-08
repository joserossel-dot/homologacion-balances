"""Pruebas adicionales de Bloque D: cifrado real openssl, rutas con espacios y códigos de salida."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import pytest

from deployment.onprem import runtime_archive


ROOT = Path(__file__).resolve().parents[2]
ONPREM = ROOT / "deployment" / "onprem"


def _make_synthetic_runtime(root: Path, marker: str = "d-synthetic-original") -> Path:
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    (root / "operational").mkdir(parents=True, exist_ok=True)
    (root / "documents" / "doc-space-1").mkdir(parents=True, exist_ok=True)
    (root / "knowledge" / "catalogo_maestro.json").write_text(
        json.dumps({"AC.01": {"nombre_estandar": "Efectivo y equivalentes"}}), encoding="utf-8",
    )
    (root / "knowledge" / "diccionario.json").write_text("[]", encoding="utf-8")
    (root / "documents" / "doc-space-1" / "content.bin").write_bytes(marker.encode("utf-8"))
    with sqlite3.connect(root / "operational" / "operations.db") as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS test_marker (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO test_marker (value) VALUES (?)", (marker,))
    return root


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible en entorno")
def test_real_openssl_direct_crypto_synthetic(tmp_path):
    """Condición 8: Cifrado y descifrado con openssl real, llaves sintéticas, y verificación de fallos."""
    data = b"Datos contables altamente confidenciales para homologacion B1\n" * 100
    plain_file = tmp_path / "plain_data.bin"
    plain_file.write_bytes(data)

    enc_file = tmp_path / "encrypted_data.bin.enc"
    key_file_good = tmp_path / "key_good.key"
    key_file_good.write_text("llave-secreta-openssl-real-12345", encoding="utf-8")

    key_file_bad = tmp_path / "key_bad.key"
    key_file_bad.write_text("llave-totalmente-distinta-99999", encoding="utf-8")

    # 1. Cifrar con openssl real pbkdf2
    cmd_enc = [
        "openssl", "enc", "-aes-256-cbc", "-salt", "-pbkdf2", "-iter", "200000",
        "-pass", f"file:{key_file_good}", "-in", str(plain_file), "-out", str(enc_file)
    ]
    res_enc = subprocess.run(cmd_enc, capture_output=True, text=True)
    assert res_enc.returncode == 0, res_enc.stderr
    assert enc_file.exists() and enc_file.stat().st_size > 0
    assert enc_file.read_bytes() != data

    # 2. Descifrar con llave correcta
    dec_file = tmp_path / "decrypted_data.bin"
    cmd_dec = [
        "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
        "-pass", f"file:{key_file_good}", "-in", str(enc_file), "-out", str(dec_file)
    ]
    res_dec = subprocess.run(cmd_dec, capture_output=True, text=True)
    assert res_dec.returncode == 0, res_dec.stderr
    assert dec_file.read_bytes() == data

    # 3. Descifrar con llave incorrecta debe fallar
    dec_bad = tmp_path / "decrypted_bad.bin"
    cmd_dec_bad = [
        "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
        "-pass", f"file:{key_file_bad}", "-in", str(enc_file), "-out", str(dec_bad)
    ]
    res_bad = subprocess.run(cmd_dec_bad, capture_output=True, text=True)
    assert res_bad.returncode != 0

    # 4. Descifrar archivo alterado debe fallar
    tampered_file = tmp_path / "tampered.enc"
    enc_bytes = bytearray(enc_file.read_bytes())
    enc_bytes[25] ^= 0xFF  # Corromper byte
    tampered_file.write_bytes(bytes(enc_bytes))
    cmd_dec_tampered = [
        "openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000",
        "-pass", f"file:{key_file_good}", "-in", str(tampered_file), "-out", str(tmp_path / "dec_tamp.bin")
    ]
    res_tamp = subprocess.run(cmd_dec_tampered, capture_output=True, text=True)
    # En CBC, corruptir un bloque intermedio puede provocar fallo de padding o texto corrupto
    assert res_tamp.returncode != 0 or (tmp_path / "dec_tamp.bin").read_bytes() != data


@pytest.mark.skipif(shutil.which("openssl") is None, reason="OpenSSL no disponible en entorno")
def test_backup_restore_with_spaces_in_paths(tmp_path):
    """Verifica que backup-runtime.sh y restore-runtime.sh soporten rutas con espacios."""
    source_dir = _make_synthetic_runtime(tmp_path / "origen con espacios", marker="spaces-verified-123")
    backup_dir = tmp_path / "destino respaldos con espacios"
    key_dir = tmp_path / "directorio llaves con espacios"
    key_dir.mkdir(parents=True)
    key_file = key_dir / "llave maestra con espacios.key"
    key_file.write_text("clave-espacios-robusta-2026", encoding="utf-8")
    key_file.chmod(0o600)

    target_dir = _make_synthetic_runtime(tmp_path / "destino restauracion con espacios", marker="anterior")

    env = {
        **os.environ,
        "RUNTIME_SOURCE_DIR": str(source_dir),
        "BACKUP_DIR": str(backup_dir),
        "ONPREM_DEPLOYMENT_MODE": "production",
        "BACKUP_ENCRYPTION_REQUIRED": "true",
        "BACKUP_ENCRYPTION_KEY_FILE": str(key_file),
    }

    # Ejecutar backup
    res_backup = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "backup-runtime.sh")],
        env=env, capture_output=True, text=True,
    )
    assert res_backup.returncode == 0, res_backup.stderr

    archives = list(backup_dir.glob("*.tar.gz.enc"))
    assert len(archives) == 1
    archive = archives[0]

    # Ejecutar restore sobre target_dir
    res_restore = subprocess.run(
        ["sh", str(ONPREM / "scripts" / "restore-runtime.sh"), str(archive), "--confirm"],
        env={**env, "RUNTIME_TARGET_DIR": str(target_dir)},
        capture_output=True, text=True,
    )
    assert res_restore.returncode == 0, res_restore.stderr

    # Verificar que el contenido restaurado tiene el marker original
    assert (target_dir / "documents" / "doc-space-1" / "content.bin").read_text(encoding="utf-8") == "spaces-verified-123"
    with sqlite3.connect(target_dir / "operational" / "operations.db") as conn:
        row = conn.execute("SELECT value FROM test_marker").fetchone()
        assert row[0] == "spaces-verified-123"


def test_restore_exit_codes_and_validation(tmp_path):
    """Verifica códigos de salida estándar de restore-runtime.sh."""
    restore_script = ONPREM / "scripts" / "restore-runtime.sh"

    # 1. Sin argumentos -> código 64 (EX_USAGE)
    res = subprocess.run(["sh", str(restore_script)], capture_output=True, text=True)
    assert res.returncode == 64

    # 2. Archivo inexistente -> código 66 (EX_NOINPUT)
    res = subprocess.run(
        ["sh", str(restore_script), str(tmp_path / "inexistente.tar.gz"), "--confirm"],
        capture_output=True, text=True,
    )
    assert res.returncode == 66

    # 3. Checksum alterado -> código 65 (EX_DATAERR)
    fake_tar = tmp_path / "fake.tar.gz"
    fake_tar.write_bytes(b"contenido-falso")
    fake_sha = tmp_path / "fake.tar.gz.sha256"
    fake_sha.write_text("0" * 64 + "\n", encoding="utf-8")
    eval_env = {
        **os.environ,
        "ONPREM_DEPLOYMENT_MODE": "evaluation",
        "BACKUP_ENCRYPTION_REQUIRED": "false",
    }
    res = subprocess.run(
        ["sh", str(restore_script), str(fake_tar), "--confirm"],
        env=eval_env, capture_output=True, text=True,
    )
    assert res.returncode == 65
