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


def round_all_number_in_dataframe(df: pd.DataFrame):
    """Round all numbers in a dataframe"""
    df = df.copy()
    for i, r in df.iterrows():
        for c in df.columns:
            if isinstance(r[c], float) and pd.notnull(r[c]):
                df.at[i, c] = round(r[c])
    return df


def detect_delimiter_from_extension(file_name: str):
    if file_name.endswith(".tsv") or file_name.endswith(".txt"):
        return "\t"
    elif file_name.endswith(".csv"):
        return ","
    else:
        return None


