# R36S Plymouth - Retomada V5 experimental (somente Colab, nunca no console)
import os, pathlib, subprocess, shutil, traceback
from google.colab import files

ROOT = pathlib.Path("/content/r36s-debian-arm64")
V4 = ROOT / "usr/local/bin/build-r36s-retomada-v4.sh"
OUT = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
LOG = pathlib.Path("/content/relatorio_plymouth_retomada_v5.txt")
TMP = ROOT / "usr/bin/systemd-tmpfiles"
BACKUP = ROOT / "usr/bin/systemd-tmpfiles.r36s-backup-original"
POLICY = ROOT / "usr/sbin/policy-rc.d"
STUB = "#!/bin/sh\n# Desabilitado somente durante compilacao no Debian isolado em QEMU/PRoot.\nexit 0\n"
print("=== R36S PLYMOUTH - RETOMADA V5 ===", flush=True)
print("Nao modifica o R36S; so o Debian temporario do Colab.", flush=True)
try:
    if not V4.is_file() or not ROOT.joinpath("var/lib/dpkg/status").is_file():
        raise RuntimeError("Nao encontrei o Debian V4 na sessao. Nao vou reinstalar do zero.")
    content = V4.read_text(encoding="utf-8")
    if "apt-get" not in content or "build-dep -y plymouth" not in content or "/debootstrap/functions" in content:
        raise RuntimeError("V4 inesperada. Preciso analisar o script antes de continuar.")

    if BACKUP.exists() or BACKUP.is_symlink():
        raise RuntimeError("Backup da rotina systemd-tmpfiles ja existe; evitando uma substituicao duplicada.")
    if not (TMP.is_file() or TMP.is_symlink()):
        raise RuntimeError("systemd-tmpfiles nao encontrado; pode ter mudado o estado do Debian. Parei.")
    TMP.rename(BACKUP)
    TMP.write_text(STUB, encoding="utf-8")
    TMP.chmod(0o755)
    print("Executavel systemd-tmpfiles preservado em backup dentro do Debian isolado.", flush=True)

    if not POLICY.exists():
        POLICY.parent.mkdir(parents=True, exist_ok=True)
        POLICY.write_text("#!/bin/sh\nexit 101\n", encoding="utf-8")
        POLICY.chmod(0o755)

    print("Tentando concluir a configuracao interrompida do systemd.", flush=True)
    cmd = ["proot", "-0", "-r", str(ROOT),
           "-b", "/dev", "-b", "/proc", "-b", "/sys",
           "-b", "/content:/content", "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root",
           "/bin/bash", "-c",
           "set -e; export LC_ALL=C LANG=C DEBIAN_FRONTEND=noninteractive SYSTEMD_OFFLINE=1; "
           "echo '[V5] Recuperando configuracao interrompida:'; "
           "dpkg --configure -a; "
           "echo '[V5] Reparando dependencias pendentes:'; "
           "apt-get -o APT::Sandbox::User=root -o APT::Sandbox::Seccomp=false -o Acquire::Retries=2 -y -f install; "
           "echo '[V5] Retomando dependencias e compilacao Plymouth:'; "
           "/bin/bash /usr/local/bin/build-r36s-retomada-v4.sh"]
    env = dict(os.environ, LC_ALL="C", LANG="C")
    last = []
    with LOG.open("w", encoding="utf-8") as report:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, bufsize=1,
                                text=True, errors="replace", env=env)
        count = 0
        for line in proc.stdout:
            report.write(line)
            report.flush()
            count += 1
            last.append(line.rstrip())
            last = last[-30:]
            if (count <= 12 or count % 100 == 0 or "[V5]" in line
                or "[4/4]" in line or "E: " in line or "ERRO:" in line
                or "error:" in line or "COMPILACAO_CONCLUIDA_ARM64" in line):
                print(line.rstrip()[:350], flush=True)
        code = proc.wait()
    print("Codigo de saida V5:", code, flush=True)
    if code == 0 and list(OUT.glob("*.deb")):
        z = shutil.make_archive("/content/Plymouth_R36S_ARM64_V5_PARA_VERIFICACAO",
                                "zip", root_dir=str(OUT))
        print("Compilacao finalizada; ainda NAO testada no R36S.", flush=True)
        files.download(z)
    else:
        print("Ainda nao finalizado. Ultimas mensagens:", flush=True)
        print("\n".join(last[-15:]), flush=True)
        files.download(str(LOG))
except Exception as exc:
    print("ERRO V5: " + str(exc), flush=True)
    with LOG.open("a", encoding="utf-8") as report:
        traceback.print_exc(file=report)
    traceback.print_exc()
    files.download(str(LOG))
finally:
    # Devolve o programa original; nao conserva stub alterando o sistema Debian.
    if BACKUP.exists() or BACKUP.is_symlink():
        if TMP.is_file() and not TMP.is_symlink():
            try:
                if TMP.read_text(encoding="utf-8") == STUB:
                    TMP.unlink()
                    BACKUP.rename(TMP)
                    print("systemd-tmpfiles original restaurado no Debian isolado.", flush=True)
                else:
                    print("Nao restaurei automaticamente: arquivo mudou; backup continua disponivel.", flush=True)
            except (UnicodeDecodeError, PermissionError, OSError):
                print("Nao consegui restaurar automaticamente; backup preservado.", flush=True)
