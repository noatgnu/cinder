from numpy.random import permutation
import pandas as pd
def scramble_dataframe(df: pd.DataFrame):
    """Scramble each cell in each column of a dataframe"""
    df = df.copy()
    for col in df.columns:
        df[col] = permutation(df[col])
    return df

def mask_column_name_with_number(df: pd.DataFrame):
    """Mask column names with numbers"""
    df = df.copy()
    df.columns = [str(i) for i in range(len(df.columns))]
    return df