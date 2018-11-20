from cirq.ops import gate_features
from cirq import ops
import cirq

# Requires use of incrementer_borrowedbit_gate.py
from cirq.ops import incrementer_borrowedbit_gate


# Source: https://algassert.com/circuits/2015/06/22/Using-Quantum-Gates-instead-of-Ancilla-Bits.html
# Implemented by: Jonathan M. Baker (jmbaker@uchicago.edu)
# Verfified on all pure state inputs up to 10 qubits.

# TODO: Documentation

class CnXLinearGate(ops.Gate, ops.TextDiagrammable, ops.ReversibleEffect, ops.CompositeGate):
	# From http://algassert.com/circuits/2015/06/22/Using-Quantum-Gates-instead-of-Ancilla-Bits.html
	def __init__(self):
		pass
	def inverse(self):
		return self
	def text_diagram_info(self):
		syms = ('@',) * (int(args.known_qubit_count) - 1)
		return ops.TextDiagramInfo(syms+('X',), connected=True)

	def default_decompose(self, qubits):
		return self._decompose(list(qubits))

	def _decompose(self, qubits):
		# qubits = [c1, c2, ..., cn, T]
		# Will "bootstrap" an ancilla
		yield ops.H(qubits[-1])
		yield CnxLinearBorrowedBit(*(qubits[:-2] + [qubits[-1]] + [qubits[-2]])).default_decompose()
		yield ops.Z(qubits[-1])**-0.25
		yield ops.CNOT(qubits[-2], qubits[-1])
		yield ops.Z(qubits[-1])**0.25
		yield CnxLinearBorrowedBit(*(qubits[:-2] + [qubits[-1]] + [qubits[-2]])).default_decompose()
		yield ops.Z(qubits[-1])**-0.25
		yield ops.CNOT(qubits[-2], qubits[-1])
		yield ops.Z(qubits[-1])**0.25
		yield ops.H(qubits[-1])

		
		# Perform a +1 Gate on all of the top bits with bottom bit as borrowed
		yield IncrementLinearWithBorrowedBitOp(*qubits)

		# Perform  -rt Z gates
		for i in range(1, len(qubits) - 1):
			yield ops.Z(qubits[i])**(-1 * 1/(2**(len(qubits) - i)))

		# Perform a -1 Gate on the top bits
		for i in range(len(qubits) - 1):
			yield ops.X(qubits[i])
		yield IncrementLinearWithBorrowedBitOp(*qubits)
		for i in range(len(qubits) - 1):
			yield ops.X(qubits[i])

		# Perform  rt Z gates
		for i in range(1, len(qubits) - 1):
			yield ops.Z(qubits[i])**(1/(2**(len(qubits) - i)))
		yield ops.Z(qubits[0])**(1/(2**(len(qubits) - 1)))

CnXLinearOp = CnXLinearGate()
"""
# Testing CnXLinearGate
for i in range(4, 9):
	for j in range(2**i):
		input_bs = format(j, '0' + str(i) + 'b')[::-1]
		output_bs = []

		# Prepare correct output bitstring
		flip = True
		for e in input_bs[:-1]:
			if int(e) == 0:
				flip = False
			output_bs.append(e)
		if flip:
			output_bs.append(str(int(input_bs[-1]) ^ 1))
		else:
			output_bs.append(input_bs[-1])
		output_bs = ''.join(output_bs)

		# Generate proper index
		input_index = sum([2**(len(input_bs)-1 - j)*int(input_bs[j]) for j in range(len(input_bs))])
		output_index = sum([2**(len(input_bs)-1 - j)*int(output_bs[j]) for j in range(len(output_bs))])
	
		g = CnXLinearGate()
		op = g(*cirq.LineQubit.range(i))
		c = cirq.Circuit.from_ops(op.default_decompose())

		state_vector = [0] * (2 ** i)
		state_vector[input_index] = 1

		sv_prime = c.apply_unitary_effect_to_state(np.array(state_vector))
		new_index = np.argmax(sv_prime)
		if output_index != new_index:
			print(input_bs, output_bs, format(new_index, '0' + str(i) + 'b'))
		#print(input_index, output_index, new_index)
		
	print(c)
"""