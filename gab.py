from __future__ import annotations  # só até o Python 3.10 (PEP 563)

import codecs
import functools
import pathlib
import shutil
import sys
import tempfile
from typing import Tuple, List  # só até Python 3.9 (PEP 585)
from typing import Optional, NamedTuple

# O py2jdbc está bugado em um dos sistemas testados.
# Plano B: tenta ler os casos fáceis na mão, e falha nos casos difíceis.
# import py2jdbc.mutf8
# codecs.register(py2jdbc.mutf8.info)

assert sys.version_info >= (3, 8)


class Gab:
    def __init__(self,
                 fmt: str,
                 num_tests: int,
                 num_items: int,
                 max_num_ans: int,
                 dont_know: bool):
        if fmt != "Formato 1":
            raise NotImplementedError(
                f"Formato '{fmt}' não reconhecido.")
        self.fmt = fmt
        self.num_tests = num_tests
        self.num_items = num_items
        self.max_num_ans = max_num_ans
        self.dont_know = dont_know

        self.testes_com_nome = None
        self.testes_sem_nome = None
        self.keys = None

    # TODO: deveria retornar uma cópia!!
    def get_test_by_st_name(self, nome: str):
        matches = []
        for t in self.testes_com_nome:
            if t.st.nome == nome:
                matches.append(t)
        if len(matches) == 0:
            raise KeyError("Nome {nome} não encontrado no .gab")
        elif len(matches) > 1:
            raise KeyError("Mais de um {nome} no .gab")
        else:
            return matches[0]

    @classmethod
    def from_gab_file(cls, path, verbose=False):
        if verbose:
            print(f"  > Arquivo {path}:")
        with _GabReader(path) as reader:
            # Cabeçalho do formato Gab
            reader.read_check_magic()
            fmt = reader.read_check_fmt()
            if verbose:
                print(f"      . formato            = {fmt}")

            # Metadados
            nt, ni, mna, dk = reader.read_check_header()
            if verbose:
                print(f"      . num_tests          = {nt}")
                print(f"      . num_items          = {ni}")
                print(f"      . max_num_answers    = {mna}")
                print(f"      . dont_know_included = {dk}")

            gab = cls(fmt, nt, ni, mna, dk)

            # Testes
            gab.testes_com_nome, gab.testes_sem_nome, gab.keys = \
                reader.read_check_tests_keys()
            if verbose:
                print("    Testes lidos:")
                print(f"      . com nome:   {len(gab.testes_com_nome)}")
                print(f"      . sem nome:   {len(gab.testes_sem_nome)}")

            reader.assert_eof()

        return gab

    @staticmethod
    def _pop_int_from_str(string):
        """Lê um dígito no início da string."""
        num_digits = 0
        while string[num_digits].isdecimal():
            num_digits += 1
        if num_digits == 0:
            raise ValueError("Linha deve começar com o número do item.")
        return int(string[:num_digits]), string[num_digits:]

    def update_from_addendum(self, path, verbose=False):
        if verbose:
            print(f"  > Arquivo {path}:")
        path = pathlib.Path(path)
        with path.open() as file:
            for line in file:
                line = line.strip()
                if not line or line[0] == '*':
                    continue
                item, line = self._pop_int_from_str(line)
                item = item - 1  # zero-based index
                if item not in range(self.num_items):
                    raise ValueError(f"Item {item + 1} não existe.")
                line = line.strip()
                if not line or line[0] != ':':
                    raise ValueError("Faltando ':'")
                line = line[1:]
                line = line.strip()
                self.keys[item] = _GabReader.MCKey(0, self.max_num_ans)
                item_str = f"{item + 1:>{len(str(self.num_items))}}"
                if line[0] == '-':
                    if verbose:
                        print(f"      . {item_str}: -")
                    pass  # mantém o self.keys[item] "==0"
                elif not line[0].isalpha():
                    raise ValueError(
                        f"Esperava as respostas corretas do item "
                        f"{item + 1}")
                else:
                    for char in line.upper():
                        if char == 'N':
                            if not self.dont_know:
                                raise ValueError(
                                    "Este gabarito não aceita "
                                    "'Não sei.'.")
                            idx = self.max_num_ans - 1
                        else:
                            idx = ord(char) - ord('A')
                            if idx not in range(self.max_num_ans):
                                raise ValueError(
                                    f"Resposta \"{char}\" inválida "
                                    f"para o item {item + 1}")
                        self.keys[item] |= 1 << idx
                    if verbose:
                        letras = self.keys[item].letras(
                            last_is_dk=self.dont_know)
                        print(f"      . {item_str}: {letras}")

    @classmethod
    def from_zip_file(cls, path, verbose=False):
        """Monta o gabarito a partir do ZIP baixado do AtenaME.

        Se esse zip tiver um .adg, lê também o adendo. Se houver um .adg
        a ser considerado que não esteja dentro do zip, use o método
        update_from_addendum do Gab retornado por este método, e.g.:

        >>> gab = Gab.from_zip_file("~/p1.zip")
        >>> gab.update_from_addendum("~/p1.adg")
        """
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmpdirname = pathlib.Path(tmpdirname)
            shutil.unpack_archive(path, tmpdirname)
            files = list(tmpdirname.iterdir())
            if len(files) != 1:
                raise ValueError(f"O zip {path} deveria ter exatamente "
                                 f"1 pasta e mais nada.")
            dirname = files[0]
            # De novo, pq são duas pastas uma dentro da outra
            files = list(dirname.iterdir())
            if len(files) != 1:
                raise ValueError(f"A pasta dentro do zip {path} "
                                 f"deveria ter dentro dela exatamente "
                                 f"1 pasta e mais nada.")
            dirname = files[0]
            # Agora encontra o .gab
            files = list(dirname.glob("*.gab"))
            if len(files) != 1:
                raise ValueError(f"Mais de um .gab dentro de {path}")
            gab_path = files[0]
            gab = cls.from_gab_file(gab_path, verbose=verbose)
            adg_path = gab_path.with_suffix(".adg")
            if adg_path.exists():
                gab.update_from_addendum(adg_path, verbose=verbose)
            return gab


def _assumes_file_open(fct):
    @functools.wraps(fct)
    def check_and_call(self, *args, **kwargs):
        self._assert_open()
        return fct(self, *args, **kwargs)
    return check_and_call


class GabReaderError(Exception):
    """Para erros do leitor de arquivos Gab."""
    pass


class GabReaderRuntimeError(GabReaderError, RuntimeError):
    """Para erros de execução do leitor."""
    pass


class GabReaderInvalidGabError(GabReaderError, ValueError):
    """Para erros que indicam que o arquivo Gab é inválido."""
    pass


class _GabReader:
    """Interface com arquivos .gab do AtenaME.

    Muitas das restrições impostas foram feitas com o objetivo de copiar
    de forma mais fiel possível o comportamento do AtenaME. Por exemplo,
    ao invés de ler a variável `num_tests' como `unsigned int', ela é
    lida como `int', e o leitor falha explicitamente caso ela não seja
    positiva.

    Obs:
    * Java sempre lê/escreve em big-endian [1]
    * Java usa um encoding próprio para strings [1]

    [1] https://docs.oracle.com/javase/7/docs/api/java/io/DataInput.html
    """

    MAGIC_v1 = 0xb3a29cd1
    MAGIC_v2 = 0xb3a29cd2

    OLD_SEPARATOR = '###'

    SIZEOF_SHORT = 2
    SIZEOF_USHORT = 2
    SIZEOF_INT = 4
    SIZEOF_UINT = 4

    ###
    ### Data classes
    ###

    # Não fazem nenhum tipo de verificação, e estão implementadas
    # como classes simplesmente porque a alternativa seria usar
    # listas/tuples e decorar as interpretações.

    class Permutation(List[int]):
        def __repr__(self):
            return f"{self.__class__.__name__}({super().__repr__()})"

        def to_csv_string(self):
            return '-'.join(map(str, self))

    class Student(NamedTuple):
        nome: str
        fields: List[str]

    class MCItem(NamedTuple):
        right: int
        num_answers: int
        perm: Permutation
        num_orig: int
        right_orig: int

    class MCTest(NamedTuple):
        perm: Permutation
        st: Student
        items: List[MCItem]

        def pprint(self):
            print(
                f"{self.__class__.__name__}(\n"
                f"    perm={self.perm},\n"
                f"    st={self.st},\n"
                f"    items=["
            )
            for i in self.items:
                print(f"        {i}")
            print(
                "    ],\n"
                ")"
            )

    class MCKey():  # bit string
        def __init__(self, i, length):
            assert i in range(2**length)
            self.length = length
            self.items = i

        def __repr__(self):
            bitstring = bin(self.items)[2:]
            items_repr = f"0b{bitstring:0>{self.length}}"
            clsname = self.__class__.__name__
            return f"{clsname}({items_repr}, length={self.length})"

        def __ior__(self, other: int):
            assert 0 <= other < 2**self.length
            self.items |= other
            return self

        def get(self, idx: int) -> bool:
            assert idx in range(self.length)
            return bool(self.items & (1 << idx))

        def letras(self, last_is_dk: bool) -> str:
            pool = [chr(ord('A') + x) for x in range(self.length)]
            if last_is_dk:
                pool[-1] = 'N'
            return ''.join(l for i, l in enumerate(pool)
                           if self.get(i))

        def perm_letras(
                self, perm: Permutation, last_is_dk: bool) -> str:
            letras = ''.join(chr(ord('A') + i)
                             for i in range(self.length - last_is_dk)
                             if self.get(perm[i]))
            if last_is_dk:
                if self.get(self.length - 1):
                    letras += 'N'
            return letras

    ###
    ### Conveniência
    ###

    def _assert_open(self):
        if not self.is_open():
            raise GabReaderRuntimeError(
                f"File '{self.path}' is not open.")

    def _raise_invalid_gab(self, txt):
        raise GabReaderInvalidGabError(
            f"{self.path}:{hex(self.file.tell())}: {txt}")

    ###
    ### Low-level read by C type
    ###

    @_assumes_file_open
    def _read_ushort(self) -> int:
        """Lê um 'unsigned short' do arquivo."""
        return int.from_bytes(self.file.read(self.SIZEOF_USHORT),
                              byteorder='big', signed=False)

    @_assumes_file_open
    def _read_int(self) -> int:
        """Lê um 'int' do arquivo."""
        return int.from_bytes(self.file.read(self.SIZEOF_INT),
                              byteorder='big', signed=True)

    @_assumes_file_open
    def _read_uint(self) -> int:
        """Lê um 'unsigned int' do arquivo."""
        return int.from_bytes(self.file.read(self.SIZEOF_UINT),
                              byteorder='big', signed=False)

    ###
    ### Read by Java type
    ###

    @_assumes_file_open
    def _read_mutf8(self) -> str:
        """Lê uma string do arquivo."""
        # Se a string a ser codificada só tiver codepoints do BMP que
        # não sejam o U+0000, a codificação dela com MUTF-8 é idêntica à
        # codificação com UTF-8. O caracter nulo U+0000 é codificado
        # como b'\xC0\x80'. Caracteres fora do BMP são codificados como
        # UTF-16 surrogate pairs. Tentar decodificar esses surrogate
        # pairs como UTF-8 gera um erro, de forma que podemos
        # simplesmente:
        # 1. escanear a string de bytes para procurar um zero (i.e. uma
        #    sequência b'\xC0\x80'). Se encontrarmos, falhamos
        #    explicitamente.
        # 2. tenta ler como UTF-8. Se detectarmos UnicodeDecodeError,
        #    falhamos também. Se não, sucesso.
        length = self._read_ushort()  # comprimento da string
        byts = self.file.read(length)
        # return codecs.decode(byts, py2jdbc.mutf8.NAME)
        if b'\xC0\x80' in byts:
            self._raise_invalid_gab(
                "Erro de decodificação unicode: U+0000 encontrado.")
        try:
            string = codecs.decode(byts, 'utf-8')
        except UnicodeDecodeError as e:
            self._raise_invalid_gab(
                f"Erro de decodificação unicode: {e}")
        return string

    ###
    ### Read Gab conventions
    ###

    @_assumes_file_open
    def _read_check_bool(self) -> bool:
        """Lê um bool (guardado como inteiro, 4 bytes) e valida.

        O comportamento do AtenaME é não verificar se o inteiro lido
        é 0/1 ou se é algo diferente, e simplesmente fazer
        'return inteiro_lido != 0;'. Aqui, vamos adicionar redundância
        verificando antes se é diferente de zero ou um.
        """
        # Se for implementar do jeito "rápido", cuidado:
        # bool(b'\x00\x00\x00\x00') é True.
        i = int.from_bytes(self.file.read(self.SIZEOF_UINT),
                           byteorder='big', signed=False)
        if i not in (0, 1):
            self._raise_invalid_gab(
                f"valor '{i}' deveria ser bool (0 ou 1).")
        return bool(i)

    ###
    ### Higher level read and check Gab fields
    ###

    @_assumes_file_open
    def read_check_magic(self) -> None:
        magic = self._read_uint()
        if magic == self.MAGIC_v1:
            raise NotImplementedError(
                f"{self.path}: formato antigo ('Gab_old'), não "
                f"suportado por este script.")
        elif magic == self.MAGIC_v2:
            return
        else:
            self._raise_invalid_gab(
                "Não é um arquivo de gabarito do AtenaME.")

    @_assumes_file_open
    def read_check_fmt(self) -> str:
        fmt = self._read_mutf8()
        if fmt != "Formato 1":
            raise NotImplementedError(
                f"{self.path}: formato desconhecido: '{fmt}'.")
        return fmt

    @_assumes_file_open
    def read_check_header(self) -> Tuple[int, int, int, bool]:
        if self.read_header:
            raise GabReaderError("Cabeçalho já foi lido!")

        num_tests = self._read_int()
        if not (num_tests > 0):
            self._raise_invalid_gab(
                f"{num_tests=} deveria ser positivo.")

        num_items = self._read_int()
        if not (num_items > 0):
            self._raise_invalid_gab(
                f"{num_items=} deveria ser positivo.")

        max_num_answers = self._read_int()
        if not (max_num_answers > 0):
            self._raise_invalid_gab(
                f"{max_num_answers=} deveria ser positivo.")

        dont_know_included = self._read_check_bool()

        # salva essas informações
        self.header_nt = num_tests
        self.header_ni = num_items
        self.header_mna = max_num_answers
        self.header_dki = dont_know_included

        self.read_header = True
        return num_tests, num_items, max_num_answers, dont_know_included

    @_assumes_file_open
    def _read_check_permutation(self) -> Permutation:
        """Lê e retorna uma permutação.

        No arquivo de dados, a permutação é gravada como 1+N
        inteiros: o primeiro inteiro diz quanto vale N, e os seguintes
        são os inteiros do range(N) na ordem especificada pela
        permutação.
        """
        N = self._read_int()
        if not (N > 0):
            self._raise_invalid_gab(
                f"`{N}' não é um valor válido para o "
                f"tamanho de uma permutação.")
        freq = [0 for _ in range(N)]
        perm = []
        for i in range(N):
            el = self._read_int()
            if el not in range(N):
                self._raise_invalid_gab(
                    f"{i}-ésimo da permutação de {N} elemento(s) não "
                    f"pode ser {el}.")
            perm.append(el)
            freq[el] += 1
        if not all(x == 1 for x in freq):
            self._raise_invalid_gab(f"{perm} não é uma permutação.")
        return self.Permutation(perm)

    @_assumes_file_open
    def _read_check_student_data(self) -> Optional[Student]:
        string = self._read_mutf8()
        if self.OLD_SEPARATOR in string:
            self._raise_invalid_gab("Formato antigo não suportado.")
        if not string:
            self._raise_invalid_gab("Dados do aluno são string vazia.")
        fields = string.split(',')
        assert fields
        if not fields[0].strip():
            # Prova sem nome, para alunos fora da pauta
            for i in range(1, len(fields)):
                if fields[i].strip():
                    self._raise_invalid_gab(
                        f"Campo inválido para prova sem nome: {fields}")
            return None
        for i in range(len(fields)):
            fields[i] = fields[i].strip()
            assert fields[i]
        nome = fields.pop(0)
        return self.Student(nome=nome, fields=fields)

    @_assumes_file_open
    def _read_check_item(self) -> MCItem:
        # permutação das respostas
        p = self._read_check_permutation()
        if len(p) != self.header_mna - self.header_dki:
            self._raise_invalid_gab(
                f"Permutação {p} deveria ter {self.header_mna} - "
                f"{int(self.header_dki)} itens.")

        # resposta certa
        c = self._read_int()
        if c not in range(len(p)):
            self._raise_invalid_gab(
                f"Resposta certa {c} não está em range({len(p)}).")

        # número de respostas (incluindo "Não sei.")
        nr = self._read_int()
        if nr != self.header_mna:
            self._raise_invalid_gab(
                f"Quantidade de respostas {c} deveria ser {len(p)} + "
                f"{int(self.header_dki)}.")

        # número original do item
        no = self._read_int()
        if no not in range(self.header_ni):
            self._raise_invalid_gab(
                f"Número original do item {c} deveria estar em "
                f"range({self.header_ni})")

        # índice original da resposta correta
        co = self._read_int()
        if co not in range(len(p)):
            self._raise_invalid_gab(
                f"Resposta certa (original) {co} não está em "
                f"range({len(p)}).")
        if co != 0:
            self._raise_invalid_gab(
                "Resposta certa original deveria ser a primeira!")
        if p[c] != co:
            self._raise_invalid_gab(
                f"Resposta certa p[{c}]={p[c]} deveria ser {co}")

        # checksum
        xor = self._read_int()
        if xor != c ^ nr ^ no ^ co:
            self._raise_invalid_gab(
                f"Item falhou o checksum: {c},{nr},{no},{co},{xor}.")

        return self.MCItem(right=c,
                           num_answers=nr,
                           perm=p,
                           num_orig=no,
                           right_orig=co)

    @_assumes_file_open
    def _read_check_test(self) -> MCTest:
        perm = self._read_check_permutation()  # permutação das questões
        st = self._read_check_student_data()
        items = []
        for i in perm:
            item = self._read_check_item()  # questão
            if item.num_orig != i:
                self._raise_invalid_gab(
                    f"Permutação dos itens {perm} em desacordo com o "
                    f"campo num_orig do {i}-ésimo item: {item}.")
            items.append(item)
        return self.MCTest(perm=perm, st=st, items=items)

    @_assumes_file_open
    def read_check_tests_keys(self) -> Tuple[
        List[MCTest], List[MCTest], List[MCKey]
    ]:
        """Retorna: testes com nome, testes sem nome, e as chaves."""
        testes_com_nome = []
        testes_sem_nome = []
        num_fields: int
        for _ in range(self.header_nt):
            t = self._read_check_test()
            if len(testes_sem_nome) == 0:
                # Todos os testes até agora foram *com* nome
                if t.st:
                    # O teste que acabamos de ler foi *com* nome
                    if len(testes_com_nome) == 0:
                        # Este é o primeiro teste do arquivo
                        num_fields = len(t.st.fields)
                    else:
                        if len(t.st.fields) != num_fields:
                            self._raise_invalid_gab(
                                f"Teste com quantidade inválida de "
                                f"campos: {t.st}")
                    testes_com_nome.append(t)
                if not t.st:
                    # Este é o primeiro teste sem nome
                    testes_sem_nome.append(t)
            else:
                if t.st:
                    self._raise_invalid_gab(
                        f"Teste com nome após teste sem nome: {t.st}")
                testes_sem_nome.append(t)
        keys = [self.MCKey(1, length=self.header_mna)
                for _ in range(self.header_ni)]
        return testes_com_nome, testes_sem_nome, keys

    @_assumes_file_open
    def assert_eof(self) -> None:
        if len(self.file.read(1)) > 0:
            self._raise_invalid_gab(
                "Dados desconhecidos no final do arquivo.")

    ###
    ### Context manager:
    ###

    def __init__(self, path):
        self.path = pathlib.Path(path).resolve()
        self.file = None
        self.read_header = False

    def __enter__(self):
        self.file = self.path.open('rb')
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self.is_open():
            self.close()

    def has_valid_handle(self):
        return self.file is not None

    def is_open(self):
        return self.has_valid_handle() and not self.file.closed

    def close(self):
        assert self.has_valid_handle()
        assert self.is_open()
        self.file.close()


MCTest = _GabReader.MCTest
MCKey = _GabReader.MCKey
MCItem = _GabReader.MCItem
