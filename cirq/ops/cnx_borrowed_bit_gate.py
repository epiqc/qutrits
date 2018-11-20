from cirq.ops import gate_features
from cirq import ops
import cirq

# Source: https://algassert.com/circuits/2015/06/05/Constructing-Large-Controlled-Nots.html
# Implemented by: Jonathan M. Baker (jmbaker@uchicago.edu)
# Verfified on all purestate inputs up to 10 qubits.

# TODO: Documentation

class CnXLinearBorrowedBitGate(ops.Gate, ops.TextDiagrammable, ops.ReversibleEffect, ops.CompositeGate):
	def __init__(self):
		pass
	def inverse(self):
		return self
	def text_diagram_info(self, args):
		syms = ('@',) * (int(args.known_qubit_count) - 2)
		return ops.TextDiagramInfo(syms+('X', 'BB'), connected=True)
	def default_decompose(self, qubits):
		# Qubits [q0, q1, ..., qn-1, qn] where qn-1 is target, qn is a borrowed bit
		qbits = list(qubits)
		if len(qbits) == 4:
			yield ops.CCX(qbits[0], qbits[1], qbits[2])
		elif len(qbits) == 3:
			yield ops.CNOT(qbits[0], qbits[1])
		elif len(qbits) == 5:
			yield ops.CCX(qbits[0], qbits[1], qbits[-1])
			yield ops.CCX(qbits[2], qbits[-1], qbits[3])
			yield ops.CCX(qbits[0], qbits[1], qbits[-1])
			yield ops.CCX(qbits[2], qbits[-1], qbits[3])
		else:
			yield self._decompose(qbits)

	def _decompose(self, qubits):
		if len(qubits) % 2 == 0:
			
			# Dumb shift fix
			l = [1, 3, 0]
			while True:
				if l[-2] + 2 > len(qubits) - 2:
					break
				l.append(l[-2] + 2)
			q = [qubits[i] for i in l]

			yield self._decompose_half(qubits[0:-3] + [qubits[-1]])
			yield self._decompose_half(q + [qubits[-1]] + [qubits[-2]])
			#yield self._decompose_half([qubits[1]] + qubits[3:-2] + [qubits[0]] + [qubits[-1]] + [qubits[-2]])
			yield self._decompose_half(qubits[0:-3] + [qubits[-1]])
			yield self._decompose_half(q + [qubits[-1]] + [qubits[-2]])
			#yield self._decompose_half([qubits[1]] + qubits[3:-2] + [qubits[0]] + [qubits[-1]] + [qubits[-2]])
		else:
			yield self._decompose_half([qubits[0]] + qubits[2:-2] + [qubits[-1]])
			yield self._decompose_half([qubits[1]] + qubits[3:-2] + [qubits[-1]] + [qubits[-2]])
			yield self._decompose_half([qubits[0]] + qubits[2:-2] + [qubits[-1]])
			yield self._decompose_half([qubits[1]] + qubits[3:-2] + [qubits[-1]] + [qubits[-2]])
	

	def _decompose_half(self, qubits):
		if len(qubits) % 2 != 0:
			# Expecting list of qubits of type [A, B, x1, C, x2, D, x3, ..., Z, T] where xi are borrowed bits
			for i in range(len(qubits) - 1, 0, -2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])

			for i in range(4, len(qubits) - 2, 2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])

			for i in range(len(qubits) - 1, 0, -2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])

			for i in range(4, len(qubits) - 2, 2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
		else:
			# Expecting list of qubits of type [A, x1, B, x2, ..., x_n-2, Z, T]
			for i in range(len(qubits) - 1, 1, -2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
			# Handle the top CNOT separately
			yield ops.CNOT(qubits[0], qubits[1])
			for i in range(3, len(qubits) - 2, 2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])

			for i in range(len(qubits) - 1, 1, -2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
			# Handle the top CNOT separately
			yield ops.CNOT(qubits[0], qubits[1])
			for i in range(3, len(qubits) - 2, 2):
				yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])

"""
# TESTING CnXLinearBorrowedBitGate on all pure states up to size 10
from itertools import product
for i in range(3,12):
	# Generate all bit strings representing which classical bits are on
	bit_strings = list(product({0,1}, repeat=i))
	for bs in bit_strings:
		output_bs = list(bs)
		controls_on = True
		for b in bs[:-2]:
			if b == 0:
				controls_on = False
		if controls_on:
			output_bs[-2] ^= 1 #(output_bs[-2] + 1) % 


		input_index = sum([2**(len(bs)-1 - j)*bs[j] for j in range(len(bs))])
		output_index = sum([2**(len(bs)-1 - j)*output_bs[j] for j in range(len(output_bs))])

		state_vector = [0] * 2 ** len(bs)
		state_vector[input_index] = 1

		g = CnXLinearBorrowedBitGate()
		op = g(*cirq.LineQubit.range(i))
		c = cirq.Circuit.from_ops(op)
	
		sv_prime = c.apply_unitary_effect_to_state(np.array(state_vector))
		new_index = np.argmax(sv_prime)
		
		if new_index != output_index:
			print(bs)
			print(output_bs)
			print(bin(new_index))
			print("NOT CORRECT")
		
	print(c)
"""
CnxLinearBorrowedBit = CnXLinearBorrowedBitGate()
