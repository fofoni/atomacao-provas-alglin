import pandas as pd


def pauta_com_notas(path='pauta_com_notas.csv'):
    df = pd.read_csv(
        path,
        index_col='numeracao',
        dtype={
            'chamada': 'string',
            'dre': 'string',
            'email': 'string',
            'nomecompleto': 'string',
            'status': 'string',
            'respostas': 'string',
            'gabarito': 'string',
        }
    )
    global num_items
    num_items = len(df['respostas'].iloc[0].split('-'))
    return df
