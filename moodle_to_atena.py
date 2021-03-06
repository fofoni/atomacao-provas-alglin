#!/usr/bin/env python3
# ./moodle_to_atena.py --help

import sys
import pathlib
import argparse
import collections

import pandas as pd

# WARNING: OS RESULTADOS GERADOS ESTARÃO ERRADOS SE VOCÊ USAR
# PYTHON 3.5 OU ANTERIOR. Se a versão for 3.6, talvez funcione.
# Para garantir que vai funcionar, use 3.7 ou mais recente.
assert sys.version_info >= (3, 7)  # We assume dicts are ordered

# TODO: deveria fazer um log automaticamente, anotando:
#       * horário que foi chamado
#       * todos os argumentos da linha de comando
#       * toda a saída do script

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
            print(
                "WARNING: faça 'pip install colorama' para que as "
                "cores funcionem de forma cross-platform.",
                file=sys.stderr)
        TermColors_Fore = collections.namedtuple(
            "TermColors_Fore", fore_dict.keys())
        Fore = TermColors_Fore(*fore_dict.values())
        TermColors_Style = collections.namedtuple(
            "TermColors_Style", style_dict.keys())
        Style = TermColors_Style(*style_dict.values())


def warn(txt):
    print(f"{Fore.RED}WARNING:{Style.RESET_ALL} {txt}", file=sys.stderr)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Gera pauta do AtenaME a partir dos CSVs do "
                    "Moodle.")

    parser.add_argument(
        "--no-colors",
        help="Se não encontrar o pacote 'colorama', não tenta usar "
             "cores.",
        action='store_false',
        dest='use_colors',
    )

    parser.add_argument(
        "--start-extra-dre-at",
        # TODO: fazer com que isso não ~dê ruim~
        help="Valor inicial para DREs coringas. De 0 a 999 (mas se o "
             "total passar de 999 vai dar ruim). O default é zero.",
        type=int,
        default=0,
    )

    parser.add_argument(
        "USUARIOS_CSV",
        help="Arquivo CSV com todos os usuários cadastrados no "
             "Moodle, conforme descrito no README.",
        type=pathlib.Path,
    )

    parser.add_argument(
        "PARTICIPANTS_CSV",
        help="Arquivo CSV com somente os usuários que vão entrar "
             "na pauta gerada, conforme descrito no README.",
        type=pathlib.Path,
    )

    # TODO: aceitar os nomes dos arquivos novos PautaAtena.{csv,xls}
    #       como parâmetros opcionais (os defaults continuarão sendo
    #       os defaults atuais)

    args = parser.parse_args()

    init()  # Inicializa as cores

    usuarios = pd.read_csv(
        args.USUARIOS_CSV, dtype={'idnumber': 'string'})

    participants = pd.read_csv(args.PARTICIPANTS_CSV)
    participants.rename(
        columns={"Endereço de email": "Email"}, inplace=True)

    pauta = []  # lista de dicts
    count_missing_dre = args.start_extra_dre_at
    for row in participants.itertuples():

        # Verifica que este email já não está na pauta
        ok = True
        for r in pauta:
            if r['email'] == row.Email:
                warn(f"O email <{row.Email}> aparece mais de uma vez "
                     f"no arquivo PARTICIPANTS_CSV. A primeira "
                     f"ocorrência deste email entrou na pauta gerada, "
                     f"mas as ocorrências seguintes NÃO vão entrar.")
                ok = False
                break
        if not ok:
            continue

        email_matches = []
        for u_row in usuarios.itertuples():
            if u_row.email == row.Email:
                email_matches.append(u_row)
        if len(email_matches) == 0:
            warn(f"O email <{row.Email}> estava presente no arquivo "
                 f"PARTICIPANTS_CSV, mas nenhum usuário com "
                 f"esse email foi encontrado no arquivo "
                 f"USUARIOS_CSV. Este usuário NÃO vai entrar na "
                 f"pauta. Se precisar, adicione este usuário "
                 f"manualmente ao arquivo USUARIOS_CSV.")
            raise RuntimeError
        if len(email_matches) > 1:
            warn(f"O email <{row.Email}>, presente no arquivo "
                 f"PARTICIPANTS_CSV, está relacionado a MAIS DE "
                 f"UM USUÁRIO de acordo com o arquivo "
                 f"USUARIOS_CSV. Somente o primeiro usuário será "
                 f"usado. Se precisar, remova manualmente as "
                 f"linhas erradas no arquivo USUARIOS_CSV.")

        nome_completo = \
            f"{email_matches[0].firstname} {email_matches[0].lastname}"
        nome_completo = nome_completo.upper()

        dre = email_matches[0].idnumber

        # TODO: gerar automaticamente um arquivo de DREs substituídos
        #       e, no final, gerar um PDF com uma tabela.
        # TODO: criar um objeto "DRE Coringa Generator" para encapsular
        #       isso aí.
        if dre is pd.StringDtype().na_value:
            dre = f"999001{count_missing_dre:03}"
            count_missing_dre += 1
            warn(f"O aluno de email <{row.Email}> e nome "
                 f"'{nome_completo}' está SEM DRE no arquivo "
                 f"PARTICIPANTS_CSV. Ele vai entrar na pauta "
                 f"com DRE={dre}.")

        # # Gambiarra para pegar alunos que colocaram 111111111 no DRE
        # if dre == "111111111":
        #     dre = f"999001{count_missing_dre:03}"
        #     count_missing_dre += 1
        #     warn(f"O aluno de email <{row.Email}> e nome "
        #          f"'{nome_completo}' se inscreveu com "
        #          f"DRE=111111111. Ele vai entrar na pauta com "
        #          f"DRE={dre}.")

        # # Gambiarra para pegar um DRE repetido
        # if dre == "115023496":
        #     dre = f"999001{count_missing_dre:03}"
        #     count_missing_dre += 1
        #     warn(f"O aluno de email <{row.Email}> e nome "
        #          f"'{nome_completo}' se inscreveu com DRE=115023496 "
        #          f"(duplicado). Ele vai entrar na pauta com "
        #          f"DRE={dre}.")

        # Verifica que este DRE já não está na pauta
        ok = True
        for r in pauta:
            if r['dre'] == dre:
                warn(f"O DRE {dre} aparece mais de uma vez "
                     f"no arquivo PARTICIPANTS_CSV. A primeira "
                     f"ocorrência deste DRE entrou na pauta "
                     f"gerada, mas as ocorrências seguintes NÃO "
                     f"vão entrar.")
                ok = False
                break
        if not ok:
            continue

        pauta.append({
            # será numerado depois de ordenar pelo nome
            'numeracao': 0,

            # todos iguais para gerar só um lote
            'chamada': 'P3AlgLin2020PLE',  # TODO: parametrizar isso

            'email': email_matches[0].email,
            'dre': dre,
            'nomecompleto': nome_completo,
        })

    pauta = sorted(pauta, key=lambda d: d['nomecompleto'])
    for i in range(len(pauta)):
        pauta[i]['numeracao'] = i + 1
    pauta_final_df = pd.DataFrame(pauta)

    # TODO: verificar se os arquivos já existem e, caso existam,
    #       perguntar se o usuário quer mesmo overwrite.
    # TODO: criar uma opção '-y'/'--overwrite' que responde "sim"
    #       automaticamente para a pergunta acima.
    pauta_final_df.to_csv(
        'PautaAtena.csv', index=False)
    pauta_final_df.to_excel(
        'PautaAtena.xls', index=False, header=False)
