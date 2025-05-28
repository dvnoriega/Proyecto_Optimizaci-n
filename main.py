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

model.update()
