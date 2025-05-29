from gurobipy import *

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
kappa = {v: 1000 for v in V}
omega = 0.7
mu = {('s1', 'nt1', t): 0.8 for t in T}  # calidad
phi = {t: 100 for t in T}
delta = {t: 50 for t in T}
C = {(i, j): 1000 for (i, j) in A}
T_sigma = {(i, j): 1 for (i, j) in A}
S_sigma = {s: 3 for s in S}
L_sigma = {s: 2000 for s in S}
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
# El estanque parte vacío, luego se verifica la conservación del flujo en el almacenamiento de agua.
for v in V:
    model.addConstr(Bv[v, 0] == 0)
    for t in T[1:]:
        model.addConstr(
            Bv[v, t] == Bv[v, t-1] +
            quicksum(AT[i, j, t] for (i, j) in A if j == v) -
            quicksum(AT[i, j, t] for (i, j) in A if i == v)
        )
# El volumen almacenado no supera la cota máxima, y si está vacío no hay agua en el estanque.  
for v in V:
    for t in T:
        model.addConstr(Bv[v, t] <= kappa[v] * (1 - y[v, t]))
        model.addConstr(z[v, t] >= y[v, t])
        model.addConstr(z[v, t] >= Bv[v, t] / kappa[v])

# Cada 48 horas se vacía el estanque. 
for v in V:
    for t in range(len(T) - 2):
        model.addConstr(y[v, t] + y[v, t+1] + y[v, t+2] >= z[v, t])

# Verificar que el agua cumpla con la calidad mínima para ser tratada y entrar al sistema.   
for (s, j, t) in mu:
    model.addConstr(e[s, j, t] * omega <= mu[s, j, t])
    model.addConstr(AT[s, j, t] <= C[s, j] * e[s, j, t])

# Se cumple con la demanda por bloque. 
for b in B:
    for t in T:
        model.addConstr(quicksum(AT[i, b, t] for (i, j) in A if j == b) >= P[b, t])

# La cantidad de agua gris que entra al sistema de trata es la misma que la que sale. 
# En caso de estar en mantención no hay flujo.
for s in S:
    for t in T:
        model.addConstr(
            quicksum(AG[i, s, t] for (i, j) in A if j == s) ==
            quicksum(AT[s, j, t] for (i, j) in A if i == s)
        )
        model.addConstr(
            quicksum(AG[i, s, t] for (i, j) in A if j == s) +
            quicksum(AT[s, j, t] for (i, j) in A if i == s) <= 2 * 100000 * (1 - m[s, t])
        ) 

# R3> El almacen con aguas tratadas solo se vac´ıa si el estanque tiene agua
model.addConstrs((z[v,t] >= y[v,t] for v in V for t in T), name = "R3")                                #Revisar 

# R4> Si el almacén tiene agua, z vale 1
model.addConstrs((z[v,t] >= Bv[v,t]/kappa[v] for v in V for t in T), name = "R4")                      #Revisar 

# R8> Asegurar que solo fluya agua tratada si se cumple calidad
model.addConstrs((AT[s,j,t] <= C[s,j]*e[s,j,t] for j in NT for s in S if (s,j) in A for t in T), name = "R8") 

# R9> El agua tratada cumple la demanda del bloque b
model.addConstrs((quicksum(AT[i,b,t] for i in N if (i,b) in A) >= P[b,t] for b in B for t in T), name = "R9")    #Falta agregar restricción para que AT no entre a B 

# R12 Alalmacén de agua tratada no entran aguas grises
model.addConstrs((quicksum(AG[i,v,t] for i in N if (i,v) in A) + quicksum(AG[v,j,t] for j in N if (v,j) in A) == 0 for v in V for t in T), name = "R12")

# R13 
model.addConstrs((quicksum(AT[v,j,t] for j in N if (v,j) in A) + quicksum(AT[i,v,t] for i in N if (i,v) in A) <=  kappa[v] * (1 - m[v,t]) for v in V for t in T), name = "R13") 

# R14 Sicumploconlacalidad,nodesechoelaguatratada
model.addConstrs((AT[j,dc,t] <= C[j,dc] * (1 - e[i,j,t]) for i in NT for j in NT if j != i and (i,j) in A for t in T for dc in DC ), name = "R14")

model.update()

