#!/usr/bin/env python3
# ./grade.py --help

from __future__ import annotations

import sys
import pathlib
import argparse
import collections
from typing import List

import pandas as pd

from gab import Gab, MCTest, MCKey

assert sys.version_info >= (3, 8)


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


def index_of_last(lst: list, x) -> int:
    return len(lst) - list(reversed(lst)).index(x) - 1


log_options = [
    'noshow',
    'one_attempt',
    'only_empty_attempts',
    'no_positive_attempts',
    'one_positive_attempt',
    'lastpos_atmost2_nonpos',
]


# TODO: essa classe está uma bagunça. Esse tipo de abstração deveria
#       ser feito de forma mais unificada com o gab.py.
class Respostas:
    # número de erradas que elimina uma certa (ou
    # então -1 para desabilitar essa funcionalidade)
    num_penalidade = 4  # TODO: deveria ser parametrizável

    last_is_dk = True  # TODO: deveria ser parametrizável

    @staticmethod
    def item_from_str(s: str, N: int) -> str:
        # s: "(a)" ou "(b)" ou ... ou "Não sei."
        # N: quantidade de itens possíveis, sem contar o "Não sei."

        # TODO: usar Unicode NCF para tirar os acentos, e comparar as
        #       strings sem acento.
        if s.lower() in ["não sei.", "nâo sei.", "não sei",
                         "não sei\xA0"]:
            return '.'
        elif (
            isinstance(s, str)
            and len(s) == 3
            and s.startswith('(')
            and s.endswith(')')
        ):
            x = ord(s[1]) - ord('a')
            if x >= N:
                raise ValueError(f"Resposta inválida: {s}.")
            return s[1]
        elif s == '-':
            return '-'
        else:
            raise ValueError(f"Resposta inválida: '{s}' ({s.encode()})")

    def _opções(self, item: int):
        return [chr(ord('a') + i) for i in range(self._N[item])]

    def __init__(self, lst: List[str], num_ans: List[int]):
        # l = ['(a)', '(d)', 'Não sei.', '(c)', ......]
        self._N = num_ans  # lista de número de itens em cada questão
        self._N = [nr - 1 for nr in self._N]
        self._l = tuple(self.item_from_str(s, N)
                        for s, N in zip(lst, num_ans))

    @classmethod
    def from_row(cls, row: pd.Series, num_ans: List[int]):
        resp_headers = []
        while (h := f'Resposta {len(resp_headers) + 1}') in row.index:
            resp_headers.append(h)
        return cls(row[resp_headers], num_ans)

    def __str__(self):
        result = ""
        for x in self._l:
            if x == '-' or x == '.':
                result += "N" + "-"
            else:
                result += x.upper() + "-"
        return result[:-1]

    def __repr__(self):
        return f'<Respostas "{self!s}">'

    def __len__(self):
        return len(self._l)

    def __iter__(self):
        yield from self._l

    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self._l == other._l
        return self == Respostas(other)

    def count(self) -> int:
        """Quantidade de respostas afirmativas (i.e. preenchidas, e
           com valor diferente de "Não sei.")"""
        return sum(x in self._opções(i) for i, x in enumerate(self._l))

    def get_item_int(self, i):
        if self._l[i] in self._opções(i):
            return ord(self._l[i]) - ord('a')
        else:
            return self._N[i]

    def iter_ints(self):
        return (self.get_item_int(i) for i in range(len(self)))

    def grade(self, test: MCTest, keys: List[MCKey]) -> float:
        """Retorna a nota (10x média de pontos), sendo que cada questão
           vale um ponto, levando em consideração a penalidade."""
        assert len(self) == len(test.items)
        assert len(self) == len(keys)
        assert len(self) == len(self._N)
        # print("GRADING: ")
        certas = 0
        erradas = 0
        gabarito = ""
        keys = [keys[i] for i in test.perm]
        for m, item, key, N in zip(
                self.iter_ints(), test.items, keys, self._N):
            # print(f"    Marcou: {m}")
            # print(f"    Item:   {item}")
            # print(f"    key:    {key}")
            # print(f"    N:      {N}")
            # #m = opção que o aluno marcou
            # #item = questão da prova do aluno
            assert N == len(item.perm)
            # TODO: verificar se o dont_know_included também bate
            # posição do item 'm' na prova original (.ate)
            po = item.perm[m] if m < N else len(item.perm)
            # print(f"    po:     {po}")
            ponto = key.get(po)
            # print(f"    ponto:  {ponto}")
            if ponto:
                certas += 1
                # print(f"    certas: {certas}")
            if m < N and not ponto:
                erradas += 1
                # print(f"    errada: {erradas}")
            # print()
            gabarito += key.perm_letras(
                item.perm, last_is_dk=self.last_is_dk) + "-"
        if self.num_penalidade >= 0:
            # implicit check that num_penalidade != 0
            certas -= erradas // self.num_penalidade
        if certas < 0:
            certas = 0
        # print(f"GRADE: {certas}")
        nota = 100 * certas
        nota = nota // len(self) + (nota % len(self) > 0)
        nota /= 10.0
        return nota, gabarito[:-1]

    def is_empty(self) -> bool:
        return all(x == '-' for x in self)

    def positive_attempt(self) -> bool:
        """Um 'positive attempt' é quando tem pelo menos uma resposta
           afirmativa."""
        return any(x in self._opções(i) for i, x in enumerate(self))


class UpdateSetAction(argparse.Action):
    __add_prefixes = '-'
    __del_prefixes = '+'

    def __init__(self,
                 option_strings,
                 dest,
                 nargs=None,
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        assert nargs is None
        assert const is None
        if default is None:
            default = set()
        if not all(o[0] in self.__add_prefixes + self.__del_prefixes
                   for o in option_strings):
            raise ValueError("Unknown prefixes")
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)
        self.__set = default.copy()

    def __call__(self, parser, namespace, values,
                 option_string=None):
        if option_string[0] in self.__add_prefixes:
            self.__set.add(values)
        elif option_string[0] in self.__del_prefixes:
            self.__set.discard(values)
        else:
            raise RuntimeError("???")
        setattr(namespace, self.dest, self.__set.copy())


def read_check_test_from_row(g, row):
    t = g.get_test_by_st_name(row.nomecompleto)
    row_fields = [
        s.replace('_', '-').replace(',', '-').replace(':', '-')
        for s in row[1:1 + len(t.st.fields)]
    ]
    if not all(x == y for x, y in zip(t.st.fields, row_fields)):
        raise ValueError("Pauta não bate com o Gab (campos diferentes)")
    return t


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Compara as respostas com o gabarito e dá as "
                    "notas.",
        prefix_chars='-+',
    )

    parser.add_argument(
        "--no-colors",
        help="Se não encontrar o pacote 'colorama', não tenta "
             "usar cores.",
        action='store_false',
        dest='use_colors',
    )

    parser.add_argument(
        "PAUTA_CSV",
        help="Arquivo de pauta gerado pelo moodle_to_atena.py.",
        type=pathlib.Path,
    )

    parser.add_argument(
        "RESPOSTAS_CSV",
        help="Respostas que os alunos deram (arquivo baixado do "
             "moodle, conforme o README). ",
        type=pathlib.Path,
    )

    parser.add_argument(
        "GABARITO",
        help="Arquivo '.gab' que foi gerado pelo AtenaME junto do lote "
             "de provas, ou então o '.zip' contendo o gab. Se for "
             "passado o zip, lemos também o '.adg' se houver.",
        type=pathlib.Path,
    )

    parser.add_argument(
        "--addendum",
        help="Arquivo '.adg' de adendo ao gabarito. Independentemente "
             "de se o GABARITO foi passado como .zip ou .gab, ou de se "
             "já havia um .adg dentro do zip, esta opção pode ser "
             "especificada várias vezes. Os adendos são processados em "
             "ordem.",
        type=pathlib.Path,
        action='append',
        metavar='ADG',
        dest='adendos',
        default=[],
    )

    parser.add_argument(
        "--log", "++log", choices=log_options,
        default={'lastpos_atmost2_nonpos'},
        action=UpdateSetAction,
        help="Quais casos avisar no stdout (ao invés de processar "
             "em silêncio)",
    )

    args = parser.parse_args()

    init()  # Inicializa as cores

    ###
    ### Ler as respostas dos alunos, e decidir qual das "tentativas"
    ### será levada em consideração.
    ###

    respostas = pd.read_csv(args.RESPOSTAS_CSV)

    pauta = pd.read_csv(args.PAUTA_CSV, index_col='numeracao',
                        dtype={
                            'chamada': 'string',
                            'email': 'string',
                            'dre': 'string',
                            'nomecompleto': 'string',
                        })
    pauta['status'] = None
    pauta['status'] = pd.Series(pauta['status'], dtype='string')
    pauta['perm'] = None
    pauta['perm'] = pd.Series(pauta['perm'], dtype='string')
    pauta['respostas'] = None
    pauta['gabarito'] = None
    pauta['gabarito'] = pd.Series(pauta['gabarito'], dtype='string')
    pauta['nota'] = float('NaN')

    # Lê o gabarito e os adendos
    if args.GABARITO.suffix == '.gab':
        g = Gab.from_gab_file(args.GABARITO, verbose=True)
    elif args.GABARITO.suffix == '.zip':
        g = Gab.from_zip_file(args.GABARITO, verbose=True)
    else:
        raise ValueError(
            f"Formato {args.GABARITO.suffix} não reconhecido.")
    for adg_path in args.adendos:
        g.update_from_addendum(adg_path, verbose=True)

    for row in pauta.itertuples():
        # todas as tentativas do aluno
        subdf = respostas[respostas['Endereço de email'] == row.email]
        stringid_aluno = f"{row.nomecompleto} <{row.email}> ({row.dre})"
        test = read_check_test_from_row(g, row)
        pauta.at[row.Index, 'perm'] = test.perm.to_csv_string()
        num_ans_list = [it.num_answers for it in test.items]

        if len(subdf) == 0:
            # Nenhuma tentativa submetiva
            status = 'noshow'
            if status in args.log:
                print(f"* Aluno não fez a prova: {stringid_aluno}")
            pauta.at[row.Index, 'status'] = status
            continue  # mantém resposta=None e nota=NaN

        # Aqui, o aluno submeteu pelo menos uma tentativa

        if len(subdf) == 1:
            # Somente uma tentativa
            status = 'one_attempt'
            if status in args.log:
                print(f"* Exatamente uma tentativa: {stringid_aluno}")
            pauta.at[row.Index, 'status'] = status
            pauta.at[row.Index, 'respostas'] = \
                Respostas.from_row(subdf.iloc[0], num_ans_list)
            nota, gabarito = pauta.at[row.Index, 'respostas'].grade(
                test, g.keys)
            pauta.at[row.Index, 'nota'] = nota
            pauta.at[row.Index, 'gabarito'] = gabarito
            continue

        # len(subdf) >= 2, ou seja, o aluno submeteu pelo menos 2
        # tentativas

        tentativas = [Respostas.from_row(r, num_ans_list)
                      for _, r in subdf.iterrows()]

        nonempty_mask = [not r.is_empty() for r in tentativas]
        if sum(nonempty_mask) == 0:
            # Todos os attempts estão vazios
            status = 'only_empty_attempts'
            if status in args.log:
                print(f"* Submeteu {len(subdf)} tentativas, todas "
                      f"vazias: {stringid_aluno}")
            pauta.at[row.Index, 'status'] = status
            pauta.at[row.Index, 'respostas'] = tentativas[-1]
            pauta.at[row.Index, 'nota'] = 0
            continue

        # pelo menos 2 tentativas, pelo menos 1 das quais é não-vazia

        positive_attempt_mask = [r.positive_attempt()
                                 for r in tentativas]

        if sum(positive_attempt_mask) == 0:
            # Nenhum attempt positivo
            status = 'no_positive_attempts'
            if status in args.log:
                print(f"* Submeteu {len(subdf)} tentativas, "
                      f"{len(subdf) - sum(nonempty_mask)} vazia(s), e "
                      f"nenhuma positiva: {stringid_aluno}")
            pauta.at[row.Index, 'status'] = status
            # salva como "resposta" a última tentativa não-vazia.
            i = index_of_last(nonempty_mask, True)
            pauta.at[row.Index, 'respostas'] = tentativas[i]
            pauta.at[row.Index, 'nota'] = 0
            continue

        # pelo menos 2 tentativas, pelo menos 1 das quais é positiva

        # Agora, decide qual a tentativa que será considerada, e
        # depois dá a nota

        idx_last_positive = index_of_last(positive_attempt_mask, True)
        last_positive_attempt = tentativas[idx_last_positive]
        num_questões = len(last_positive_attempt)
        last_positive_count = last_positive_attempt.count()

        # Primeiro: decide qual tentativa será considerada...

        effective_attempt_idx = None

        if sum(positive_attempt_mask) == 1:
            # Exatamente uma tentativa positiva
            status = 'one_positive_attempt'
            if status in args.log:
                print(f"* Submeteu {len(subdf)} tentativas, exatamente "
                      f"uma delas positiva: {stringid_aluno}")
            pauta.at[row.Index, 'status'] = status
            # salva como "resposta" a única tentativa positiva.
            effective_attempt_idx = positive_attempt_mask.index(True)

        # se o último (entre os positivos) tem no máx. 2 entradas
        # não-positivas, retorna ele
        elif last_positive_count >= num_questões - 2:
            status = 'lastpos_atmost2_nonpos'
            if status in args.log:
                print(f"* Submeteu {len(subdf)} tentativas, a última "
                      f"positiva com {last_positive_count:>2} itens: "
                      f"{stringid_aluno}")
            pauta.at[row.Index, 'status'] = status
            effective_attempt_idx = idx_last_positive

        # ...e só agora dá a nota

        if effective_attempt_idx is not None:
            effective_attempt = tentativas[effective_attempt_idx]
            pauta.at[row.Index, 'respostas'] = effective_attempt
            nota, gabarito = effective_attempt.grade(test, g.keys)
            pauta.at[row.Index, 'nota'] = nota
            pauta.at[row.Index, 'gabarito'] = gabarito
            continue

        subdf = subdf.copy()
        subdf.drop(
            ['Sobrenome', 'Nome', 'Endereço de email', 'Avaliar/10,00'],
            axis=1, inplace=True)
        raise NotImplementedError(
            f"Você está encontrando este erro porque o seguinte "
            f"aluno:\n\n    {stringid_aluno}\n\n"
            f"submeteu um padrão de tentativas que não cai em nenhum "
            f"dos casos testados por este script. Estas foram as "
            f"{len(subdf)} tentativas:\n\n{subdf}\n\n"
            f"1) Dê uma olhada no código para ver quais casos são "
            f"contemplados;\n"
            f"2) Descubra (talvez perguntando para o aluno) o que "
            f"exatamente aconteceu, e qual das tentativas que ele "
            f"submeteu deve ser levada em consideração;\n"
            f"3) Adapte o código para levar em consideração o caso do "
            f"aluno, e Tente Outra Vez."
        )

    print(f"Stats: (total {len(pauta)})")
    total_count = 0
    for opt in log_options:
        count = 0
        for comp in pauta.status == opt:
            if comp is not pd.StringDtype().na_value and comp:
                count += 1
        print(f"  > {opt}: {count}")
        total_count += count
    na_count = 0
    for stat in pauta.status:
        if stat is pd.StringDtype().na_value:
            na_count += 1
    assert na_count == 0
    assert total_count == len(pauta)

    pauta.to_csv('pauta_com_notas.csv')
