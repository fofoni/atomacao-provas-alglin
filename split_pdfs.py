#!/usr/bin/env python3
# ./split_pdfs.py --help

import sys
import tempfile
import pathlib
import os
import shutil
import subprocess
import argparse
import collections
from math import log10, floor

import pandas as pd

from pdfrw import PdfReader, PdfWriter, IndirectPdfDict

# TODO: ler o PDF a partir do ZIP, ao invés de forçar o usuário a baixar
#       o PDF solto.

# WARNING: OS RESULTADOS GERADOS ESTARÃO ERRADOS SE VOCÊ USAR
# PYTHON 3.5 OU ANTERIOR. Se a versão for 3.6, talvez funcione.
# Para garantir que vai funcionar, use 3.7 ou mais recente.
assert sys.version_info >= (3, 7)  # We assume dicts are ordered


# TODO: tornar o 'colorama' obrigatório.
try:
    from colorama import init, Fore, Style
except ModuleNotFoundError:
    def init():
        global Fore, Style
        global args
        fore_dict = {
            'RED': "\033[91m",
        }
        style_dict = {
            'RESET_ALL': "\033[0m",
        }
        if not args.use_colors:
            for d in fore_dict, style_dict:
                for k in d:
                    d[k] = ""
        else:
            print("WARNING: faça 'pip install colorama' para que as "
                  "cores funcionem de forma cross-platform.",
                  file=sys.stderr)
        TermColors_Fore = collections.namedtuple(
            "TermColors_Fore", fore_dict.keys())
        Fore = TermColors_Fore(*fore_dict.values())
        TermColors_Style = collections.namedtuple(
            "TermColors_Style", style_dict.keys())
        Style = TermColors_Style(*style_dict.values())


def warn(txt):
    print(f"{Fore.RED}WARNING:{Style.RESET_ALL} {txt}",
          file=sys.stderr)


def error(txt):
    print(f"{Fore.RED}ERROR:{Style.RESET_ALL} {txt}",
          file=sys.stderr)


def find_name_in_pdf(name, filename):
    result = subprocess.run(
        ['pdfgrep', name, os.fspath(filename)],
        stdout=subprocess.DEVNULL)
    return result.returncode == 0


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Separa o PDF de lote de provas em um para cada "
                    "DRE.")

    parser.add_argument(
        "--no-colors",
        help="Se não encontrar o pacote 'colorama', não tenta "
             "usar cores.",
        action='store_false',
        dest='use_colors',
    )

    parser.add_argument(
        "LOTE_PDF",
        help="Arquivo de lote de provas, gerado pelo AtenaME.",
        type=pathlib.Path,
    )

    parser.add_argument(
        "SKIP_PAGES",
        help="Quantidade de páginas de lista de presença no início "
             "do LOTE_PDF, conforme o README.",
        type=int,
    )

    parser.add_argument(
        "PAUTA_CSV",
        help="Arquivo de pauta gerado pelo moodle_to_atena.py.",
        type=pathlib.Path,
    )

    # TODO: criar o known_values.csv automaticamente caso não exista.
    #       essa opção deve passar a ser opcional
    parser.add_argument(
        "KNOWN_VALUES_CSV",
        help="Tabela de DREs verificados manualmente, conforme "
             "descrito no README.",
        type=pathlib.Path,
    )

    parser.add_argument(
        "PROVAS_DIR",
        help="Nome de diretório (inexistente) onde as provas "
             "serão salvas. O mesmo nome (seguido de .zip) "
             "será usado para o zip. Leia o README.",
        type=pathlib.Path,
    )

    args = parser.parse_args()

    init()  # Inicializa as cores

    ### Lê o arquivo de pauta
    pauta_atena = pd.read_csv(
        args.PAUTA_CSV,
        index_col='numeracao',
        dtype={'dre': 'string'})
    assert pauta_atena['dre'].is_unique
    assert pauta_atena['email'].is_unique
    if not pauta_atena['nomecompleto'].is_unique:
        warn("Nomes (completos!) repetidos:")
        mask = pauta_atena['nomecompleto'].duplicated(keep=False)
        masked_df = pauta_atena.loc[mask]
        print(masked_df[['email', 'dre', 'nomecompleto']],
              file=sys.stderr)

    ### Lê o arquivo de known values
    known_values = pd.read_csv(
        args.KNOWN_VALUES_CSV,
        index_col='pgnum',
        dtype={'dre': 'string'})
    assert known_values.index.is_unique, \
        "Entradas duplicadas no arquivo de 'known values'."

    ### Dict que diz quais páginas do PDF de lote estão associadas
    ### a cada DRE.
    dre_to_pages_map = {dre: [] for dre in pauta_atena['dre']}

    ### Faz todo o trabalho dentro de um diretório temporário
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = pathlib.Path(tmpdirname)

        ### Cria diretórios dentro do diretório temporário
        # Diretório com um arquivo para cada página
        pages_dir = tmpdir / "pages"
        pages_dir.mkdir()
        # Diretório com um arquivo para cada prova (que pode ter mais
        # de uma página)
        final_dir = tmpdir / "final"
        final_dir.mkdir()

        print("> Separando as páginas...", end='')
        lote_reader = PdfReader(os.fspath(args.LOTE_PDF))
        for i, page in enumerate(lote_reader.pages):
            if i < args.SKIP_PAGES:
                continue
            page_writer = PdfWriter()
            page_writer.addpages([page])
            page_writer.write(os.fspath(pages_dir / f"{i+1:08}.pdf"))
        del page_writer, lote_reader, page
        print()

        num_files = len(list(pages_dir.iterdir()))
        num_files_digits = floor(log10(num_files + args.SKIP_PAGES)) + 1
        for i, filename in enumerate(sorted(pages_dir.iterdir())):
            pgnum = int(filename.stem)
            assert i + 1 == pgnum - args.SKIP_PAGES
            print(f"\r> Procurando nomes em cada página:"
                  f"{pgnum: {num_files_digits}}"
                  f"/{num_files + args.SKIP_PAGES}",
                  end='')
            names_found = []
            for row in pauta_atena.itertuples():
                if find_name_in_pdf(row.nomecompleto, filename):
                    names_found.append(row)
            if len(names_found) != 1:
                for row in known_values.itertuples():
                    if row.Index == pgnum:
                        dre = row.dre
                        if dre not in dre_to_pages_map:
                            dre_to_pages_map[dre] = []
                        break
                else:
                    print()
                    error(f"Não foi possível encontrar qual o nome "
                          f"da página {pgnum} do lote de provas. "
                          f"Leia manualmente esta página, e "
                          f"adicione o DRE do aluno ao arquivo de "
                          f"'known values'.")
                    raise ValueError()
            else:
                dre = names_found[0].dre
            dre_to_pages_map[dre].append(filename)
        print()

        ### Verifica que os nomes foram encontrados sequencialmente,
        ### na ordem correta, e que todo nome apareceu em pelo menos
        ### uma página.
        prev_max = None
        print("> Validando os nomes encontrados...", end='')
        print_newline = True
        for i, dre in enumerate(dre_to_pages_map):
            if len(dre_to_pages_map[dre]) == 0:
                if print_newline:
                    print()
                    print_newline = False
                warn(f"O DRE {dre} está presente na pauta, mas não foi "
                     f"encontrado no lote! Ele vai ficar sem prova!")
                continue
            this_min = min(
                int(file.stem) for file in dre_to_pages_map[dre])
            this_max = max(
                int(file.stem) for file in dre_to_pages_map[dre])
            if prev_max is not None:
                assert this_min == prev_max + 1
            prev_max = this_max
        print()

        print("> Gerando os arquivos finais...", end='')
        for dre in dre_to_pages_map:
            prova_writer = PdfWriter()
            for filename in dre_to_pages_map[dre]:
                prova_writer.addpages(PdfReader(filename).pages)
            prova_writer.trailer.Info = IndirectPdfDict(
                Title=f"P1 AlgLin 2020 PLE: {dre}")
            prova_writer.write(os.fspath(final_dir / f"{dre}.pdf"))
        print()

        provas_dir = (pathlib.Path() / args.PROVAS_DIR).resolve()
        print(f"> Colocando as provas no diretório {provas_dir} ...",
              end='')
        provas_dir.mkdir()
        for filename in final_dir.iterdir():
            shutil.copyfile(
                os.fspath(filename),
                os.fspath(provas_dir / filename.name)
            )
        print()

    print("> Gerando o zip...", end='')
    shutil.make_archive(
        os.fspath(provas_dir), "zip",
        root_dir=os.fspath(provas_dir.parent),
        base_dir=os.fspath(provas_dir.name)
    )
    print()
