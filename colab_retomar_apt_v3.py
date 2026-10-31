# Continuar o Plymouth sem refazer Debian 13: execute numa NOVA celula do MESMO notebook Colab V3.
import pathlib, subprocess, shutil, traceback
from google.colab import files

ROOT = pathlib.Path("/content/r36s-debian-arm64")
SOURCE = ROOT / "usr/local/bin/build-r36s.sh"
LOG = pathlib.Path("/content/relatorio_retomada_apt_plymouth.txt")
OUTPUT = pathlib.Path("/content/plymouth-r36s-arm64-pacotes")
print("R36S Plymouth: retomada da V3, sem reinstalar a base Debian.")

if not SOURCE.is_file() or not (ROOT / "usr/lib/apt/methods/http").is_file():
    print("ERRO: nao encontrei os arquivos da V3 neste ambiente.")
    print("Isto ocorre se o Colab reiniciou/desconectou ou se voce abriu outro notebook em outra sessao.")
    print("Nao execute a V3 novamente por enquanto. Avise o ChatGPT.")
else:
    original = SOURCE.read_text(encoding="utf-8")
    if "apt-get build-dep -y plymouth" not in original:
        raise RuntimeError("Script da V3 inesperado. Nao fiz alteracoes; envie o relatorio.")
    # Evita reinstalar o Debian e tenta executar o APT sem seu sandbox
    # isolado, que pode falhar combinado ao QEMU + PRoot.
    modified = original.replace(
        "test -s /debootstrap/functions || { echo \"ERRO: /debootstrap/functions nao encontrado no Debian ARM64\"; exit 1; }",
        "echo 'Debian ARM64 instalado na V3; ignorando verificacao de debootstrap.'",
        1
    ).replace(
        "DEBOOTSTRAP_DIR=/debootstrap /debootstrap/debootstrap --second-stage",
        "echo 'Segundo estagio ja concluido na V3; prosseguindo.'",
        1
    ).replace(
        "apt-get update",
        "apt-get -o APT::Sandbox::User=root -o APT::Sandbox::Seccomp=false -o Acquire::Retries=2 update",
        1
    ).replace(
        "apt-get install -y --no-install-recommends",
        "apt-get -o APT::Sandbox::User=root -o APT::Sandbox::Seccomp=false -o Acquire::Retries=2 install -y --no-install-recommends",
        1
    ).replace(
        "apt-get build-dep -y plymouth",
        "apt-get -o APT::Sandbox::User=root -o APT::Sandbox::Seccomp=false -o Acquire::Retries=2 build-dep -y plymouth",
        1
    )
    destination = ROOT / "usr/local/bin/build-r36s-retomada.sh"
    destination.write_text(modified, encoding="utf-8")
    destination.chmod(0o755)
    cmd = ["proot", "-0", "-r", str(ROOT),
           "-b", "/dev", "-b", "/proc", "-b", "/sys",
           "-b", "/content:/content",
           "-b", "/etc/resolv.conf:/etc/resolv.conf",
           "-q", "/usr/bin/qemu-aarch64-static",
           "-w", "/root", "/bin/bash", "-lc",
           "export LANG=C LC_ALL=C; echo 'Verificando APT no Debian ARM64:'; "
           "ls -l /usr/lib/apt/methods/http; "
           "dpkg --print-architecture; "
           "echo 'Retomando instalacao de dependencias / build:'; "
           "/bin/bash /usr/local/bin/build-r36s-retomada.sh"]
    print("Conferindo o componente HTTP e retomando as dependencias.")
    print("Dependendo da rede e da emulacao, isso ainda pode demorar.")
    tail = []
    with LOG.open("w", encoding="utf-8") as report:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", bufsize=1)
        n = 0
        for line in proc.stdout:
            report.write(line)
            report.flush()
            n += 1
            tail.append(line.rstrip())
            tail = tail[-30:]
            if ("ERRO:" in line or "Error" in line or "error:" in line
                or "COMPILACAO_CONCLUIDA_ARM64" in line or n % 100 == 0):
                print(line.rstrip()[:300])
        code = proc.wait()
    print("Codigo final:", code)
    if code == 0 and list(OUTPUT.glob("*.deb")):
        zip_path = shutil.make_archive("/content/Plymouth_R36S_ARM64_Retomada", "zip",
                                       root_dir=str(OUTPUT))
        print("Pacotes criados, mas ainda NAO validados no R36S.")
        files.download(zip_path)
    else:
        print("Retomada nao concluida. Ultimas mensagens:")
        print("\n".join(tail[-15:]))
        files.download(str(LOG))
