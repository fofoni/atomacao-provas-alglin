# 1. Baixar a pauta do Moodle

No Moodle, baixamos 2 CSVs. Um com *todos* os usuários do moodle
inteiro, que contém todas as informações de identificação, e outro
sem muita informação, mas que tem somente os usuários que queremos.

* "Administração do Site" > "Usuários" > "Contas/Ações em lote sobre
    usuários" > "Usuários na lista/Adicione todos". Agora, lá em baixo
    em "Com usuários selecionados...", escolha "Download" e clique em
    "Vai". Selecione que quer exportar como CSV, e clique em "Download".
    Vamos chamar o arquivo baixado de `Usuarios.csv`.
* Na página inicial do curso, clique na engrenagem (lá em cima à
    direita) e depois em "Mais..." para ir para a página de
    "Administração do curso". Agora, na aba "Usuários", vamos em
    "Usuários/Usuários inscritos". No "Corresponder", selecione
    "Grupos", e então selecione quais grupos queremos. (Para gerar
    a pauta de alunos para os quais vamos gerar PDFs de provas.) Agora,
    "Aplicar filtros". Por fim, lá em baixo, "Selecione todos os *N*
    usuários" e "Com usuários selecionados..." escolha "Baixar dados
    da tabela como" CSV. Vamos chamar esse arquivos de
    `participants.csv`.

O primeiro arquivo (`Usuarios.csv`) deve ter as colunas:
`username`, `email`, `firstname`, `lastname`, `idnumber` (entre outras,
e não necessariamente nessa ordem).

O segundo arquivo
(`participants.csv`) deve ter as colunas:
`Nome`, `Sobrenome`, `Endereço de email` (novamente: pode haver
outras colunas, e a ordem não precisa ser essa).


# 2. Gerar a pauta para o AtenaME


## 2.1. Gambiarras

Dê uma olhada nas partes do arquivo `moodle_to_atena.py` que estão
marcadas como "gambiarra", e verifique que é isso mesmo que você quer.
Se não for, delete essas partes.


## 2.2. Rodar o script

(ATENÇÃO: o script a seguir cria os arquivos `PautaAtena.csv` e
`PautaAtena.xls`, e deleta o conteúdo anterior desses arquivos caso
existissem.)

Use o comando:

```
$ ./moodle_to_atena.py Usuarios.csv participants.csv
```

para gerar os arquivos `PautaAtena.csv` e `PautaAtena.xls`.
Você provavelmente vai querer salvar a saída desse script (todos
os "warnings") em algum lugar.


# 3. Gerar o lote de provas

Use o AtenaME, com o arquivo de pauta `PautaAtena.xls`, para gerar
o PDF do lote de testes. Vamos chamar esse pdf de `Lote.pdf`.
Baixe também a base de correção, `Lote.gab`.


# 4. Separando os PDFs


## 4.1. `pdfgrep`

Certifique-se de que você tem o `pdfgrep` instalado no seu sistema.
Procure por `pdfgrep` no package manager da sua distribuição, ou então
baixe de um dos sites:

* https://pdfgrep.org/
* https://gitlab.com/pdfgrep/pdfgrep
* https://sourceforge.net/projects/pdfgrep


## 4.2. Arquivo `known_values.csv`

Crie um arquivo `known_values.csv` (o nome não precisa ser esse)
com somente uma linha:

```
pgnum,dre
```

Ou seja, é um CSV que é uma tabela vazia. Se o script a seguir
não conseguir descobrir qual o nome do aluno referente a uma
certa página do pdf de lote de provas, você vai precisar adicionar
uma linha neste CSV de 'known values'. Por exemplo, se o script
não conseguir descobrir o nome que está na página 32, você vai
precisar descobrir manualmente qual o nome do aluno, procurar
o DRE dele no arquivo `PautaAtena.csv` (digamos que o DRE é
123456789), e adicionar a seguinte linha ao `known_values.csv`:

```
32,123456789
```

Em particular, você deve gerar uma linha dessas (ou mais de uma linha,
caso as provas tenham mais de uma página) para cada prova
extra (sem nome, fora da pauta) gerada pelo Atena.


## 4.3. Rodando o script

Faça:

```
./split_pdfs.py Lote.pdf <N> PautaAtena.csv known_values.csv Provas
```

onde `N` é a quantidade de páginas de "lista de presença" no início
do arquivo `Lote.pdf`, e `Provas` é o nome de um diretório
*inexistente*. Atenção:

* Se o diretório
    já existir, o script vai dar um erro e não vai fazer nada (mas o
    erro é só no final, e vc vai perder tempo, pq ele é lerdo).
* `Provas` deve ser somente um *nome*, e não um path inteiro. O
    diretório será criado no `$PWD`.

Quando o script terminar de executar, as provas estarão no diretório
`Provas/`. Além disso, ele salva uma versão "zipada" desse diretório,
com o mesmo nome, terminando com `.zip` (por exemplo, `Provas.zip`),
também no `$PWD`.


# 5. Correção


## 5.1. Baixar as respostas

Antes de mais nada, certifique-se de que o horário de submissão das
respostas já passou!

No Moodle, abra o questionário, vá na engrenagem, e debaixo de
"Resultados", clique em "Respostas". Em "Baixar dados da tabela como",
certifique-se de que a opção selecionada é CSV, e clique em "Download".
Vamos chamar o arquivo baixado de `Respostas.csv`.


## 5.2. (TODO)
