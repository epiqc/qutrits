import cirq
from cirq import qutrit
import numpy as np

g = qutrit.BTBCnUGate(); op = g(*cirq.LineQubit.range(14)); c = cirq.Circuit.from_ops(op.default_decompose(), strategy=cirq.InsertStrategy.EARLIEST)


def get_random_state(n):
    rand_state2 = np.zeros(2 ** n, np.complex64)
    rand_state2.real = np.random.randn(2 ** n)
    rand_state2.imag = np.random.randn(2 ** n)
    rand_state2 /= np.linalg.norm(rand_state2)
    rand_state3 = np.zeros(3 ** n, np.complex64)
    for i, val in enumerate(rand_state2):
        rand_state3[int(bin(i)[2:], 3)] = val
    return rand_state3

while(1):
    print(c.apply_unitary_effect_to_state(get_random_state(14))[0])
