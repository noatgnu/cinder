import json
import os
from typing import List

import openai
import pandas as pd
from cinder.utility import scramble_dataframe, mask_column_name_with_number
# data = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[
#         {
#             "role": "system", "content": "Assume a data analyst role"
#         },
#         {
#             "role": "user", "content": "The tabulated data below has 11 rows with the first row being header. Identify the column with sample intensity data. Do not include any explanations and return only in a RFC8259 compliant json array without deviation of the numeric index of those column with the following example: [1,2,3,4]"
#         },
#         {
#             "role": "user", "content": """C: Phosphatase	C: Kinase	N: NumberPSM	T: Index	T: Gene	4Hr-AGB1.01	4Hr-AGB1.02	4Hr-AGB1.03	4Hr-AGB1.04	4Hr-AGB1.05	24Hr-AGB1.01	24Hr-AGB1.02	24Hr-AGB1.03	24Hr-AGB1.04	24Hr-AGB1.05	4Hr-Cis.01	4Hr-Cis.02	4Hr-Cis.03	24Hr-Cis.01	24Hr-Cis.02	24Hr-Cis.03
#         +	16	Q2M2I8	AAK1	1398743.504	1392166.178	1507472.235	1419252.645	1469608.046	1692588.689	1678452.176	1549530.799	1603841.34	1561498.768	1424969.886	1442160.198	1402724.251	1640495.266	1711464.575	1617013.172
#         +	8	P00519	ABL1	395440.1957	377312.4031	406473.0003	375590.2274	319199.7509	325162.1935	303850.0492	274738.5822	262362.136	339370.1148	392980.99	375668.3373	524724.2719	330181.5542	333124.0528	332685.6239
#         +	17	P42684	ABL2	868279.5019	828648.0768	802198.6429	828877.8587	862700.3406	717092.6476	777562.9758	758663.1821	809908.8356	737457.3042	798260.4452	840099.1024	856325.6415	770053.9505	723784.1554	803367.1808
#         +	8	Q04771	ACVR1	1027566.264	1152551.671	1084576.21	983250.8481	1129693.521	1154390.579	1201995.446	1238875.688	1201412.376	1150556.181	1097660.138	1032922.083	1129145.523	1142687.911	1174650.388	1181345.884
#         +	1	P36896	ACVR1B	61889.19773	92265.26501	63823.49531	88592.68736	75757.44212	158277.8667	147576.144	155515.6236	184837.7619	179895.5532	85985.15588	105662.2126	118991.5829	190073.7793	163859.5236	171232.8529
#         +	4	Q86TW2	ADCK1	773638.4643	610825.1758	732617.1763	731348.7468	643018.1792	508892.0049	549667.6316	573208.3102	590181.8384	641060.0593	765265.0569	693290.276	662334.2785	662288.3706	579359.7766	707906.8451
#         +	7	Q3MIX3	ADCK5	744700.0867	758663.1821	796823.1296	751805.5291	802754.8774	534896.4117	512218.5587	571343.9554	589895.5498	601956.6211	781507.3954	895292.7637	818827.483	585009.2862	552264.5508	662380.1896
#         +	20	P31749	AKT1	9758310.781	9104194.824	9664073.524	8834395.561	9247295.113	8002392.717	8181307.523	7318923.32	7911939.699	7348406.474	9225527.668	8945929.759	8537605.084	7686524.536	7347897.139	7545578.071
#         +	16	P31751	AKT2	13929112.47	15083835.64	14258313.39	15641765.24	15217204.34	15914075.36	14996266.15	15898639.73	14997305.65	15261569.49	14293937.01	15729832.8	15330484.96	15810722.94	15633094	16240582.02
#         """
#         }
#     ])


async def gpt_get_index(data: pd.DataFrame, api_key: str = "") -> List[int]:
    if not api_key:
        openai.api_key = os.environ.get("OPENAI_API_KEY", None)
    if openai.api_key is None:
        raise ValueError("OPENAI_API_KEY not found")
    res = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo", messages=[
        {
            "role": "system", "content": "Assume a bioinformatician role",
        },
        {
            "role": "user", "content": f"""The tabulated data below has {data.shape[0]+1} rows and {len(data.columns)} columns with the first row being header. Each row is separated by a newline symbol '\\n'. Can you identify the name of columns with only sample intensity data?
                                       Do not include any explanations and return only in a RFC8259 compliant json array without deviation following the example: ["column_name_1","column_name_2","column_name_3"]"""
        },
        {
            "role": "user", "content": mask_column_name_with_number(scramble_dataframe(data)).to_csv(index=False, sep="\t")
        }
    ])
    result = []
    for i in json.loads(res["choices"][0]["message"]["content"]):
        result.append(data.columns[int(i)])
    return result

async def gpt_index_with_json(data: pd.DataFrame, api_key: str = "") -> List[int]:
    if not api_key:
        openai.api_key = os.environ.get("OPENAI_API_KEY", None)
    if openai.api_key is None:
        raise ValueError("OPENAI_API_KEY not found")
    res = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo", messages=[
        {
            "role": "system", "content": "Assume a bioinformatician role",
        },
        {
            "role": "user", "content": f"""The dataframe in dictionary format below has {data.shape[0]} rows and {len(data.columns)} columns. Can you identify the name of columns with only sample intensity data?
                                       Do not include any explanations and return only in a RFC8259 compliant json array without deviation following the example: ["column_name_1","column_name_2","column_name_3"]"""
        },
        {
            "role": "user", "content": mask_column_name_with_number(scramble_dataframe(data)).to_dict()
        }
    ])
    result = []
    for i in json.loads(res["choices"][0]["message"]["content"]):
        result.append(data.columns[int(i)])
    return result

def get_index(data: pd.DataFrame, api_key: str = "") -> List[int]:
    if not api_key:
        openai.api_key = os.environ.get("OPENAI_API_KEY", None)
    if openai.api_key is None:
        raise ValueError("OPENAI_API_KEY not found")
    meta = f"""The tabulated data below has {data.shape[0] + 1} rows and {len(data.columns)} columns with the first row being header. Each row is separated by a newline symbol '\\n'. Can you identify the name of columns with only sample intensity data? Do not include any explanations and return only in a RFC8259 compliant json array without deviation following the example: ["column_name_1", "column_name_2", "column_name_3"]"""

    res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[
        {
            "role": "system", "content": "Assume a bioinformatician role",
        },
        {
            "role": "user", "content": f"""The tabulated data below has {data.shape[0]+1} rows and {len(data.columns)} columns with the first row being header. Each row is separated by a newline symbol '\\n'. Can you identify the name of columns with only sample intensity data?
                                       Do not include any explanations and return only in a RFC8259 compliant json array without deviation following the example: ["column_name_1","column_name_2","column_name_3"]"""
        },
        {
            "role": "user", "content": scramble_dataframe(data).to_csv(index=False, sep="\t")
        }
    ])
    return json.loads(res["choices"][0]["message"]["content"])

def get_index_json(data: pd.DataFrame, api_key: str = "") -> List[int]:
    if not api_key:
        openai.api_key = os.environ.get("OPENAI_API_KEY", None)
    if openai.api_key is None:
        raise ValueError("OPENAI_API_KEY not found")
    meta = f"""The dataframe in json format below contains sample intensity data where each key is a column name. Can you identify the name of columns with only sample intensity data? Do not include any explanations and return only in a RFC8259 compliant json array without deviation following the example: ["column_name_1","column_name_2","column_name_3"]"""

    res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[
        {
            "role": "system", "content": "Assume a bioinformatician role",
        },
        {
            "role": "user", "content": meta
        },
        {
            "role": "user", "content": json.dumps(scramble_dataframe(data).to_dict())
        }
    ])
    return json.loads(res["choices"][0]["message"]["content"])
