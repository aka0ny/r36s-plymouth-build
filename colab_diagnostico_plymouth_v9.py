# R36S Plymouth - V9 diagnostico de caminhos (somente Colab)
# Nao modifica nem o Debian isolado nem o SD do R36S.
import pathlib, subprocess, os, traceback
from google.colab import files

root = pathlib.Path("/content/r36s-debian-arm64")
log = pathlib.Path("/content/relatorio_plymouth_diagnostico_v9.txt")
pkg = root / "var/cache/apt/archives/debhelper_13.24.2_all.deb"

with log.open("w", encoding="utf-8") as f:
    def emit(s):
        s = str(s)
        print(s, flush=True)
        f.write(s + "\n")
        f.flush()

    emit("=== R36S PLYMOUTH V9 - DIAGNOSTICO DE CAMINHOS ===")
    try:
        emit("[HOST] Estado dos caminhos dentro do Debian:")
        for rel in [".", "usr", "usr/bin", "usr/bin/dh", "usr/bin/perl",
                    "bin", "usr/share/perl5/Debian/Debhelper", 
                    "usr/local/bin/continuar-plymouth-v8.sh",
                    "root/plymouth-work/plymouth-24.004.60"]:
            p = root / rel
            emit(f"{rel}: exists={p.exists()} is_file={p.is_file()} is_symlink={p.is_symlink()}")
            if p.is_symlink():
                emit(f"  symlink->{os.readlink(p)}")
            if p.is_file() and rel == "usr/bin/dh":
                emit(f"  first_bytes={p.read_bytes()[:80]!r} size={p.stat().st_size}")
        emit("[HOST] Conteudo de alguns diretórios:")
        for rel in ["usr/bin", "bin", "usr/share/perl5/Debian"]:
            p = root / rel
            if p.is_dir():
                for item in list(p.iterdir()):
                    if item.name.startswith("dh") or item.name.startswith("debhelper"):
                        emit(f"  {rel}/{item.name}")
        emit("[HOST] Versao do pacote APT:")
        if pkg.is_file():
            p = subprocess.run(["dpkg-deb", "-f", str(pkg), "Version"],
                               text=True, capture_output=True)
            emit(f"  cache={pkg.stat().st_size} bytes; version={p.stdout.strip()} ({p.returncode})")
        else:
            emit("  nao disponivel no cache")

        probe = ("echo '[GUEST] PWD:'; pwd; echo '[GUEST] ARCH:'; dpkg --print-architecture; "
                 "echo '[GUEST] usr/bin:'; ls -ld / /usr /usr/bin /usr/bin/dh /bin /usr/bin/perl 2>&1; "
                 "echo '[GUEST] Readlink:'; readlink /usr/bin/dh 2>&1 || true; "
                 "echo '[GUEST] dpkg list:'; dpkg -L debhelper 2>&1 | grep -E '(/usr/bin/dh$|/usr/share/perl5/Debian/Debhelper)' | head -n 10; "
                 "echo '[GUEST] dh variants:'; find /usr/bin -maxdepth 1 -name 'dh*' -print | head -n 20; "
                 "echo '[GUEST] dh execute:'; if [ -x /usr/bin/dh ]; then /usr/bin/dh --help 2>&1 | head -n 4; else echo 'NAO EXECUTAVEL'; fi")
        opts = ["-0", "-r", str(root),
                "-b", "/dev", "-b", "/proc", "-b", "/sys",
                "-b", "/etc/resolv.conf:/etc/resolv.conf",
                "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root"]
        tests = [
            ("Com mapeamento /content (igual V8)", ["-b", "/content:/content"]),
            ("Sem mapeamento /content", []),
        ]
        dhpath = root / "usr/bin/dh"
        if dhpath.is_file():
            tests.append(("Com bind explicito do dh", ["-b", f"{dhpath}:/usr/bin/dh"]))
        for label, extras in tests:
            emit("\n=== TESTE: " + label + " ===")
            cmd = ["proot"] + opts + extras + ["/bin/bash", "-c", probe]
            try:
                p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors="replace", timeout=100,
                                   env=dict(os.environ, LC_ALL="C", LANG="C"))
                emit("RETORNO: " + str(p.returncode))
                emit(p.stdout[-8500:])
            except Exception as e:
                emit("ERRO DO TESTE: " + repr(e))
        emit("=== DIAGNOSTICO CONCLUIDO; SEM ALTERACOES ===")
    except Exception:
        emit("ERRO NO DIAGNOSTICO:")
        emit(traceback.format_exc())

files.download(str(log))
