# R36S Plymouth: retomada segura V4 da sessao Colab V3.
import os, pathlib, subprocess, shutil, traceback
from google.colab import files

root = pathlib.Path("/content/r36s-debian-arm64")
source = root / "usr/local/bin/build-r36s.sh"
out = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
log = pathlib.Path("/content/relatorio_plymouth_retomada_v4.txt")

print("=== R36S PLYMOUTH - RETOMADA V4 ===", flush=True)
print("Sem reinstalar Debian ou modificar o R36S.", flush=True)
try:
    if not source.is_file():
        raise RuntimeError("Nao encontrei ambiente V3 nesta sessao do Colab.")
    original = source.read_text(encoding="utf-8")
    lines = original.splitlines()
    check = [x for x in lines if x.strip().startswith("test -s /debootstrap/functions")]
    stage = [x for x in lines if x.strip().startswith("DEBOOTSTRAP_DIR=/debootstrap /debootstrap/debootstrap --second-stage")]
    if len(check) != 1 or len(stage) != 1:
        raise RuntimeError("Nao encontrei exatamente as duas linhas para remover. Nao modifiquei o script original.")
    lines = [x for x in lines if x not in check and x not in stage]
    script = "\n".join(lines) + "\n"
    script = script.replace("apt-get update\n", "echo '[V4] Listas APT obtidas na V3.'\n", 1)
    script = script.replace(
        "apt-get install -y --no-install-recommends ca-certificates curl quilt dpkg-dev build-essential fakeroot file",
        "echo '[V4] Ferramentas de compilacao instaladas na V3.'", 1)
    script = script.replace(
        "apt-get build-dep -y plymouth",
        "apt-get -o APT::Sandbox::User=root -o APT::Sandbox::Seccomp=false -o Acquire::http::Pipeline-Depth=0 -o Acquire::Retries=2 build-dep -y plymouth", 1)
    if "/debootstrap/functions" in script or "debootstrap --second-stage" in script or "APT::Sandbox::User=root" not in script:
        raise RuntimeError("Validacao da V4 falhou, sem iniciar compilacao.")
    dest = root / "usr/local/bin/build-r36s-retomada-v4.sh"
    dest.write_text(script, encoding="utf-8")
    dest.chmod(0o755)
    print("V4: verificacao e instalacao do debootstrap removidas e validadas.", flush=True)
    print("Iniciando somente as dependencias do Plymouth.", flush=True)

    cmd = ["proot", "-0", "-r", str(root),
           "-b", "/dev", "-b", "/proc", "-b", "/sys",
           "-b", "/content:/content", "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static", "-w", "/root",
           "/bin/bash", "-c",
           "export LC_ALL=C LANG=C; echo '[V4] ARQUITETURA:'; dpkg --print-architecture; "
           "echo '[V4] INICIANDO:'; /bin/bash /usr/local/bin/build-r36s-retomada-v4.sh"]
    env = dict(os.environ, LANG="C", LC_ALL="C")
    last = []
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1, env=env)
        n = 0
        for line in proc.stdout:
            fh.write(line)
            fh.flush()
            n += 1
            last.append(line.rstrip())
            last = last[-25:]
            if n <= 10 or n % 50 == 0 or "[4/4]" in line or "ERRO:" in line or "E: " in line or "error:" in line or "COMPILACAO_CONCLUIDA_ARM64" in line:
                print(line.rstrip()[:300], flush=True)
        code = proc.wait()
    print("Codigo de saida V4:", code, flush=True)
    if code == 0 and list(out.glob("*.deb")):
        z = shutil.make_archive("/content/Plymouth_R36S_ARM64_V4_PARA_VERIFICACAO", "zip", root_dir=str(out))
        print("Pacotes gerados; ainda NAO testados no console.")
        files.download(z)
    else:
        print("Retomada V4 incompleta, ultimas linhas:\n" + "\n".join(last[-15:]))
        files.download(str(log))
except Exception as exc:
    print("ERRO V4: " + str(exc), flush=True)
    with log.open("a", encoding="utf-8") as fh:
        traceback.print_exc(file=fh)
    traceback.print_exc()
    files.download(str(log))
