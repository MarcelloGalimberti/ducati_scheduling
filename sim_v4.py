# env ducati_simulated_orders
# costruire requirements.txt
# Importazione librerie
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import streamlit as st
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')
from PIL import Image
from datetime import datetime
import plotly.express as px

# Impostazioni Layout
st.set_page_config(layout="wide")
url_immagine = 'https://github.com/MarcelloGalimberti/Sentiment/blob/main/Ducati_red_logo.png?raw=true'

col_1, col_2 = st.columns([1, 3])
with col_1:
    st.image(url_immagine, width=150)
with col_2:
    st.title('Scheduling MSV4 MTO')

# Caricamento dati
st.subheader('Caricamento dati', divider='red')

uploaded_op_raw = st.file_uploader("Carica ordini pianificati (Planned_Order_SO_20240417_simulato.XLSX)") # Planned_Order_SO_20240417_simulato.XLSX
if not uploaded_op_raw:
    st.stop()
df_op_raw=pd.read_excel(uploaded_op_raw, parse_dates=True)

# Visualizza file
#st.write('Ordini pianificati')
#st.dataframe(df_op_raw)


uploaded_cadenze = st.file_uploader("Carica cadenze (cadenze MTS MaGa.XLSX)") # cadenze MTS MaGa.XLSX
if not uploaded_cadenze:
    st.stop()
df_cadenze=pd.read_excel(uploaded_cadenze, skiprows=[1])

# Visualizza file
#st.write('Cadenze')
#st.dataframe(df_cadenze)

# Pre-processing ordini pianificati
# Moltiplicazione righe
righe_duplicate = []
for _, row in df_op_raw.iterrows():
    # Duplica la riga tante volte quante indicato dal valore nella colonna 'valore'
    for _ in range(row['Qtà ordine pian.']):
        # Aggiungi la riga duplicata alla lista delle righe duplicate
        righe_duplicate.append(row)
df_op = pd.DataFrame(righe_duplicate)
df_op.reset_index(drop=True, inplace=True)

# Esplode descrizione
df_descrizione = df_op['Descrizione materiale'].str.split(expand=True)
df_descrizione.rename(columns = {0: 'Versione', 1:'MY',2:'Std_nazione',3:'Colore',4:'Ruote',5:'STD',6:'Plant'}, inplace=True)
df_op = df_op.merge(df_descrizione,left_index=True, right_index=True)

# Aggiunge mese-anno CDD
df_op['CDD_mese_inizio_cardine']=df_op['Data inizio cardine'].dt.month
df_op['CDD_anno_inizio_cardine']=df_op['Data inizio cardine'].dt.year

# Sorting per anno-mese
df_op.sort_values(by = ['CDD_anno_inizio_cardine', 'CDD_mese_inizio_cardine'], inplace=True)
df_op.reset_index(inplace=True, drop = True)
df_op['qty_chart']=1
df_op['anno_mese'] = df_op['Data inizio cardine'].dt.strftime('%Y-%m')


# Visualizza df_op
#st.write('df_op')
#st.dataframe(df_op)

# Grafico ordini pianificati

fig = px.bar(df_op, x= "anno_mese", y='qty_chart', title= 'Ordini pianificati',color='Versione')
st.plotly_chart(fig, use_container_width=True)


# Assegnazione radar per clustering
def assegna_radar(df):
    contiene_i = df['materiale'].str.contains('I')
    contiene_radar = df['materiale'].isin(['MSV4RS', 'MSV4PP'])
    df['Radar'] = 0
    df.loc[contiene_i | contiene_radar, 'Radar'] = 1  
    return df

# Creazione df RS e V21E
df_RS = df_op[df_op['Versione']=='MSV4RS']
df_RS.reset_index(inplace=True, drop=True)
df_V21E = df_op[df_op['Versione'].isin(['MSV4', 'MSV4S', 'MSV4PP', 'MSV4SI', 'MSV4STI','MSV4STIP'])] # Eliminata MSV4RI
df_V21E.reset_index(inplace=True, drop=True)

# Pre-processing cadenze
df_cadenze['data'] = pd.to_datetime(df_cadenze['Short Description'], format='%d.%m.%y')
df_cadenze.drop(columns=['Short Description'], inplace=True)
df_cadenze = df_cadenze.loc[df_cadenze['MTS_V4_MY_24'] != 99]
df_cadenze = df_cadenze[['data','MTS_V21E','MTSV4_RS']]

# Visualizza cadenze processate
#st.write('Cadenze processate')
#st.dataframe(df_cadenze)

# Grafico cadenze processate
fig_cadenze = px.bar(df_cadenze,x='data',y=['MTS_V21E','MTSV4_RS'], title='Cadenze MTO')
st.plotly_chart(fig_cadenze, use_container_width=True)

# Crea cadenze RS e V21E
cad_RS = df_cadenze[['data','MTSV4_RS']]
cad_RS = cad_RS[cad_RS['MTSV4_RS']!=0]
cad_RS.reset_index(inplace=True, drop = True)
cad_V21E = df_cadenze[['data','MTS_V21E']]
cad_V21E = cad_V21E[cad_V21E['MTS_V21E']!=0]
cad_V21E.reset_index(inplace=True, drop = True)

# Scheduling
# RS
df_materiali_MTSV4_RS = df_RS[['Ordine','Versione','CDD_mese_inizio_cardine','CDD_anno_inizio_cardine']]
df_materiali_MTSV4_RS.rename(columns = {'Versione':'Linea'}, inplace=True)
df_cadenza_MTSV4_RS = cad_RS

df_scheduling_MTSV4_RS = pd.DataFrame(columns = ['data','capacity','materiale','cap_residua','ID'])
df_scheduling_MTSV4_RS.loc[0, 'cap_residua'] = 9999
moto_schedulate = []
n = 0
for i in range(len(df_cadenza_MTSV4_RS)):
    if len(moto_schedulate) == len(df_materiali_MTSV4_RS): # se finiscono le moto smette di schedulare
        break    
    df_scheduling_MTSV4_RS.iloc[-1, 3]=9999
    while df_scheduling_MTSV4_RS.iloc[-1, 3] > 0:
        if n >= len(df_materiali_MTSV4_RS): # aggiunge condizione di uscita se finiscono le moto
            break
        df_scheduling_MTSV4_RS.loc[n, 'data'] = df_cadenza_MTSV4_RS.loc[i, 'data']
        df_scheduling_MTSV4_RS.loc[n, 'capacity'] = df_cadenza_MTSV4_RS.loc[i, 'MTSV4_RS']
        df_scheduling_MTSV4_RS.loc[n, 'materiale'] = df_materiali_MTSV4_RS.loc[n, 'Linea']
        df_scheduling_MTSV4_RS.loc[n, 'ID'] = df_materiali_MTSV4_RS.loc[n, 'Ordine']#
        df_scheduling_MTSV4_RS.loc[n, 'cap_residua'] = df_cadenza_MTSV4_RS.loc[i, 'MTSV4_RS']-(df_scheduling_MTSV4_RS[df_scheduling_MTSV4_RS['data'] == df_cadenza_MTSV4_RS.loc[i, 'data']].shape[0])
        moto_schedulate.append(df_scheduling_MTSV4_RS.loc[n, 'materiale'])
        n += 1
df_scheduling_MTSV4_RS.drop(columns=['cap_residua'], inplace=True)

# V21E
df_materiali_V21E = df_V21E[['Ordine','Versione','CDD_mese_inizio_cardine','CDD_anno_inizio_cardine']]
df_materiali_V21E.rename(columns = {'Versione':'Linea'}, inplace=True)
df_cadenza_V21E = cad_V21E

df_scheduling_V21E = pd.DataFrame(columns = ['data','capacity','materiale','cap_residua','ID'])
df_scheduling_V21E.loc[0, 'cap_residua'] = 9999
moto_schedulate = []
n = 0
for i in range(len(df_cadenza_V21E)):
    if len(moto_schedulate) == len(df_materiali_V21E): # se finiscono le moto smette di schedulare
        break    
    df_scheduling_V21E.iloc[-1, 3]=9999
    while df_scheduling_V21E.iloc[-1, 3] > 0:
        if n >= len(df_materiali_V21E): # aggiunge condizione di uscita se finiscono le moto
            break
        df_scheduling_V21E.loc[n, 'data'] = df_cadenza_V21E.loc[i, 'data']
        df_scheduling_V21E.loc[n, 'capacity'] = df_cadenza_V21E.loc[i, 'MTS_V21E']
        df_scheduling_V21E.loc[n, 'materiale'] = df_materiali_V21E.loc[n, 'Linea']
        df_scheduling_V21E.loc[n, 'ID'] = df_materiali_V21E.loc[n, 'Ordine']#
        df_scheduling_V21E.loc[n, 'cap_residua'] = df_cadenza_V21E.loc[i, 'MTS_V21E']-(df_scheduling_V21E[df_scheduling_V21E['data'] == df_cadenza_V21E.loc[i, 'data']].shape[0])
        moto_schedulate.append(df_scheduling_V21E.loc[n, 'materiale'])
        n += 1
df_scheduling_V21E.drop(columns=['cap_residua'], inplace=True)

# Scheduling complessivo
df_scheduling = pd.concat([df_scheduling_MTSV4_RS,df_scheduling_V21E],axis=0,ignore_index=True)

# Aggiunta radar per clustering
df_scheduling=assegna_radar(df_scheduling)

# Visualizza df_scheduling
#st.write('df_scheduling')
#st.dataframe(df_scheduling)

st.subheader('Sequenziamento linea Multistrada - MTO', divider='red')

# Sequencing
df_sc = df_scheduling.copy()

def sequenzia_giorno(df_scheduling):
    df_conteggi = df_scheduling['Radar'].value_counts().rename_axis('id_cluster').reset_index(name='counts')
    df_conteggi=df_conteggi.astype('int')
    lunghezza_residua = len(df_scheduling)
    lista_start = list(np.arange(0,len(df_scheduling),1))
    for i in range(len(df_conteggi)):
        posizioni=[]
        posizioni =list(np.linspace(0,
                                lunghezza_residua-1,
                                list(df_conteggi.loc[i,['counts']])[0],
                                dtype='int'))
        lunghezza_residua = lunghezza_residua-list(df_conteggi.loc[i,['counts']])[0]
        lista_indici = list(map(lambda x: lista_start[x],posizioni))
        k=0
        numero_cluster = list(df_conteggi.loc[i,['id_cluster']])[0]
        for j in df_scheduling[df_scheduling['Radar']==numero_cluster].index:
            df_scheduling.at[j,'sequenza']=lista_indici[k]
            k=k+1
        lista_start=list(np.delete(lista_start,posizioni))
    df_sequenziato = df_scheduling.sort_values(by=['sequenza'])
    return df_sequenziato

# Ciclo per giorno
giorni = list(df_sc['data'].unique())

df_sequenced = pd.DataFrame(columns = ['data', 'capacity', 'materiale', 'ID', 'Radar', 'sequenza'])
for giorno in giorni:
    df_giorno = df_sc[df_sc['data'] == giorno]
    df_sequenziato_giorno = sequenzia_giorno(df_giorno)
    df_sequenced = pd.concat([df_sequenced,df_sequenziato_giorno], ignore_index=True)

df_sequenced['data'] = pd.to_datetime(df_sequenced['data'])
df_sequenced['data'] = df_sequenced['data'].dt.date
df_sequenced['qty'] = 1
df_sequenced['data_sequenza'] = df_sequenced['data'].astype(str) + ' ' + df_sequenced['sequenza'].astype(str)

# Visualizza df_sequenced
st.write('df_sequenced')
st.dataframe (df_sequenced)

#df_sequenced_chart = df_sequenced[df_sequenced['data'].astype(str)=='2024-09-20']
#st.write(df_sequenced_chart)

# Grafico df_sequenced

fig_sequenced = px.bar(df_sequenced, x= 'data_sequenza', y='qty', title= 'Ordini sequenziati',color='Radar',category_orders={'data_sequenza': df_sequenced['data_sequenza']})
st.plotly_chart(fig_sequenced, use_container_width=True)

# Export xlsx

def scarica_excel(df, filename):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Sheet1')
    writer.close()
    st.download_button(
        label="Download file di output per ECC",
        data=output.getvalue(),
        file_name=filename,
        mime="application/vnd.ms-excel"
    )

# df_output per ECC
df_output = df_sequenced[['data','ID']]
df_output.rename(columns = {'data':'data inizio cardine','ID':'Ordine pianificato'}, inplace=True)
df_output['data inizio cardine'] = pd.to_datetime(df_output['data inizio cardine'])
df_output['data fine cardine'] = df_output['data inizio cardine'] + pd.tseries.offsets.BDay(1)
df_output = df_output[['Ordine pianificato','data inizio cardine','data fine cardine']]

# Visualizza df_output
st.write('df_output')
st.dataframe(df_output)


scarica_excel(df_output, 'df_output')


