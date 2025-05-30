from gurobipy import *
import pandas
import os

# --- Crear el modelo ---
model = Model("Reutilizacion_Aguas_Grises")

# --- Conjuntos (Ejemplo inicial) ---
B = ['b1', 'b2']  # Edificios
S = ['s1']        # Sistemas de tratamiento
V = ['v1']        # Estanques
NG = ['ng1']      # Nodos disposición aguas grises
NT = ['nt1']      # Nodos disposición aguas tratadas
DC = ['dc']       # Eliminación por mala calidad
DV = ['dv']       # Eliminación por tiempo de almacenamiento
T = range(30)     # Días del mes

N = B + S + V + NG + NT + DC + DV
A = [(i, j) for i in N for j in N if i != j]

# --- Parámetros (ejemplo simplificado) ---
gamma = {'s1': 42084}
kappa = {v: 1000 for v in V}
omega = 0.7
mu = {('s1', 'nt1', t): 0.8 for t in T}  # calidad
phi = {t: 100 for t in T}
delta = {t: 50 for t in T}
C = {(i, j): 1000 for (i, j) in A}
T_sigma = {(i, j): 1 for (i, j) in A}
S_sigma = {s: 3 for s in S}
L_sigma = {s: 436099 for s in S}
L_sigma.update({v: 0 for v in V}) 
O = {(b, t): 500 for b in B for t in T}
P = {(b, t): 400 for b in B for t in T}

# --- Variables de decisión (inicial) ---
AG = model.addVars(A, T, lb=0, name="AG")  # Agua gris
AT = model.addVars(A, T, lb=0, name="AT")  # Agua tratada
x = model.addVars(A, T, vtype=GRB.BINARY, name="x")  # Uso de arco
e = model.addVars(S, NT, T, vtype=GRB.BINARY, name="e")  # Calidad
m = model.addVars(S + V, T, vtype=GRB.BINARY, name="m")  # Mantención
y = model.addVars(V, T, vtype=GRB.BINARY, name="y")      # Vaciado
z = model.addVars(V, T, vtype=GRB.BINARY, name="z")      # Tiene agua
Bv = model.addVars(V, T, lb=0, name="Bv")                # Agua almacenada
Di = model.addVars(NG, T, lb=0, name="Di")               # Desecho agua gris
Ht = model.addVars(T, lb=0, name="Ht")                   # Desecho agua tratada


# --- Restricciones ---
# R1 Y R2: El estanque parte vacío, luego se verifica la conservación del flujo en el almacenamiento de agua.
for v in V:
    model.addConstr(Bv[v, 0] == 0)
    for t in T[1:]:
        model.addConstr(
            Bv[v, t] == Bv[v, t-1] +
            quicksum(AT[i, j, t] for (i, j) in A if j == v) -
            quicksum(AT[i, j, t] for (i, j) in A if i == v), 
            name = "R2"
        )

# R3: El almacen con aguas tratadas solo se vacía si el estanque tiene agua
model.addConstrs((z[v,t] >= y[v,t] for v in V for t in T), name = "R3") 

# R4: Si el almacén tiene agua, z vale 1
model.addConstrs((z[v,t] >= Bv[v,t]/kappa[v] for v in V for t in T), name = "R4")

# R5: Cada 48 horas se vacía el estanque. 
for v in V:
    for t in range(len(T) - 2):
        model.addConstr(y[v, t] + y[v, t+1] + y[v, t+2] >= z[v, t])

# R6: El volumen almacenado no supera la cota máxima, y si está vacío no hay agua en el estanque.  
for v in V:
    for t in T:
        model.addConstr(Bv[v, t] <= kappa[v] * (1 - y[v, t]))
        model.addConstr(z[v, t] >= y[v, t])
        model.addConstr(z[v, t] >= Bv[v, t] / kappa[v], name = "R6")

#R7: Verificar que el agua cumpla con la calidad mínima.  
for (s, j, t) in mu:
    model.addConstr(e[s, j, t] * omega <= mu[s, j, t])
    model.addConstr(AT[s, j, t] <= C[s, j] * e[s, j, t], name = "R7")

# R8:Asegurar que solo fluya agua tratada si se cumple calidad
model.addConstrs((AT[s,j,t] <= C[s,j]*e[s,j,t] for j in NT for s in S if (s,j) in A for t in T), name = "R8") 

# R9: Se cumple con la demanda del bloque b. 
model.addConstrs((quicksum(AT[i, b, t] for i in N if (i, b) in A) >= P[b, t] for b in B for t in T), name="R9")

# R10: La cantidad de agua gris que entra al sistema de trata es la misma que la que sale. 
for s in S:
    for t in T:
        model.addConstr(
            quicksum(AG[i, s, t] for (i, j) in A if j == s) ==
            quicksum(AT[s, j, t] for (i, j) in A if i == s)
        )
        model.addConstr(
            quicksum(AG[i, s, t] for (i, j) in A if j == s) +
            quicksum(AT[s, j, t] for (i, j) in A if i == s) <= 2 * gamma[s] * (1 - m[s, t]),
            name = "R10"
        ) 

#R12: Al almacén de agua tratada no entran aguas grises
model.addConstrs((
    quicksum(AG[i, v, t] for i in N if (i, v) in A) +
    quicksum(AG[v, j, t] for j in N if (v, j) in A) == 0
    for v in V for t in T
), name="R12")

#R12: Alalmacén de agua tratada no entran aguas grises
model.addConstrs((quicksum(AG[i,v,t] for i in N if (i,v) in A) + quicksum(AG[v,j,t] for j in N if (v,j) in A) == 0 for v in V for t in T),name = "R12")

#R13 
model.addConstrs((quicksum(AT[v,j,t] for j in N if (v,j) in A) + quicksum(AT[i,v,t] for i in N if (i,v) in A) <=  kappa[v] * (1 - m[v,t]) for v in V for t in T), name = "R13") 

#R14: Si cumplo con la calidad,no desecho el agua tratada.
model.addConstrs((
    AT[j, dc, t] <= C[j, dc] * (1 - e[s, j, t])
    for s in S for j in NT for dc in DC for t in T
    if (j, dc) in A and (s, j, t) in e
), name="R14")

#R15: Si no se vacía el alamcén, no se elimina el agua tratada.
model.addConstrs((
    AT[v, dv, t] <= kappa[v] * y[v, t]
    for v in V for dv in DV if (v, dv) in A for t in T
), name="R15")

#R16: Definicion de Ht.
model.addConstrs((
    Ht[t] == quicksum(AT[i, dc, t] for i in N for dc in DC if (i, dc) in A) +
             quicksum(AT[i, dv, t] for i in N for dv in DV if (i, dv) in A)
    for t in T
), name="R16")

# R17: Balance de aguas grises.
model.addConstrs((
    quicksum(AG[i, ng, t] for i in N if (i, ng) in A) -
    quicksum(AG[ng, j, t] for j in N if (ng, j) in A) ==
    quicksum(O[b, t] for b in B) -
    Di[ng, t] -
    quicksum(AG[i, s, t] for i in N for s in S if (i, s) in A)
    for ng in NG for t in T
), name="R17")


#R18: Balance de aguas tratadas en toda la red.
model.addConstrs((
    quicksum(AT[j, n, t] for j in N for n in NT + V if (j, n) in A) -
    quicksum(AT[n, j, t] for n in NT + V for j in N if (n, j) in A) -
    quicksum(AT[j, b, t] for j in N for b in B if (j, b) in A) ==
    quicksum(AT[i, s, t] for i in N for s in S if (i, s) in A) - Ht[t]
    for t in T
), name="R18")


#R19: Se hace mínimo una mantención mensual al sistema.
model.addConstrs((quicksum(m[s, t] for t in T) >= 1 for s in S), name="R19")

#R20: No superar el caudal máximo de los arcos.
model.addConstrs((
    AG[i, j, t] + AT[i, j, t] <= C[i, j] * x[i, j, t]
    for (i, j) in A for t in T
), name="R20")

#R21: Balance de nodos intermedios.
model.addConstrs((
    quicksum(AG[i, n, t] + AT[i, n, t] for i in N if (i, n) in A) ==
    quicksum(AG[n, j, t] + AT[n, j, t] for j in N if (n, j) in A)
    for n in NG + NT for t in T
), name="R21")

# --- Función Objetivo ---
model.setObjective(
    quicksum(T_sigma[i, j] * (AG[i, j, t] + AT[i, j, t]) for (i, j) in A for t in T) +
    quicksum(S_sigma[s] * quicksum(AG[i, s, t] for i in N if (i, s) in A) for s in S for t in T) +
    quicksum(m[i, t] * L_sigma[i] for i in S + V for t in T) +
    quicksum(delta[t] * Di[ng, t] for ng in NG for t in T) +
    quicksum(phi[t] * Ht[t] for t in T),
    GRB.MINIMIZE
)

# --- Resolver modelo ---
model.optimize()

# --- Resultados función objetivo ---
if model.status == GRB.OPTIMAL:
    print(f"\nCosto mínimo total: {model.ObjVal}")
    for (i, j, t) in AG.keys():
        if AG[i, j, t].X > 0:
            print(f"AG[{i},{j},{t}] = {AG[i,j,t].X}")


# --- Crear excel con resultados básicos ---
if model.status == GRB.OPTIMAL:
    # AG - Agua Gris
    ag_data = []
    for (i, j, t) in AG.keys():
        val = AG[i, j, t].X
        if val > 0.1:
            ag_data.append({'Día': t, 'Origen': i, 'Destino': j, 'Litros Agua Gris': val})

    df_ag = pd.DataFrame(ag_data)

    # AT - Agua Tratada
    at_data = []
    for (i, j, t) in AT.keys():
        val = AT[i, j, t].X
        if val > 0.1:
            at_data.append({'Día': t, 'Origen': i, 'Destino': j, 'Litros Agua Tratada': val})

    df_at = pd.DataFrame(at_data)

    # Mantenciones (m)
    m_data = []
    for i in S + V:
        for t in T:
            val = m[i, t].X
            if val > 0.9:
                m_data.append({'Día': t, 'Nodo': i, 'Mantención': 1})

    df_m = pd.DataFrame(m_data)

    # Vaciados (y)
    y_data = []
    for v in V:
        for t in T:
            val = y[v, t].X
            if val > 0.9:
                y_data.append({'Día': t, 'Estanque': v, 'Vaciado': 1})

    df_y = pd.DataFrame(y_data)

    # Desechos Agua Gris (Di)
    di_data = []
    for (i, t) in Di.keys():
        val = Di[i, t].X
        if val > 0.1:
            di_data.append({'Día': t, 'Nodo': i, 'Litros Desecho Agua Gris': val})

    df_di = pd.DataFrame(di_data)

    # Desechos Agua Tratada (Ht)
    ht_data = []
    for t in T:
        val = Ht[t].X
        if val > 0.1:
            ht_data.append({'Día': t, 'Litros Desecho Agua Tratada': val})

    df_ht = pd.DataFrame(ht_data)

    # Crea archivo Excel
    with pd.ExcelWriter('resultados_modelo_aguas_grises.xlsx') as writer:
        df_ag.to_excel(writer, sheet_name='AG_Agua_Gris', index=False)
        df_at.to_excel(writer, sheet_name='AT_Agua_Tratada', index=False)
        df_m.to_excel(writer, sheet_name='Mantenciones', index=False)
        df_y.to_excel(writer, sheet_name='Vaciados', index=False)
        df_di.to_excel(writer, sheet_name='Desechos_Agua_Gris', index=False)
        df_ht.to_excel(writer, sheet_name='Desechos_Agua_Tratada', index=False)

    print("Resultados exportados a 'resultados_modelo_aguas_grises.xlsx'")