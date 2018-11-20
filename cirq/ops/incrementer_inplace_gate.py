from cirq.ops import gate_features
from cirq import ops
import cirq

# Requires use of cnx_linear_gate.py and incrementer_borrowedbit_gate.py
from cirq.ops import incrementer_borrowedbit_gate


# Source: Extension from the following series of blog post:
#	https://algassert.com/circuits/2015/06/22/Using-Quantum-Gates-instead-of-Ancilla-Bits.html
# Implemented by: Jonathan M. Baker (jmbaker@uchicago.edu)
# Verfified on all pure state inputs up to 10 qubits.

# TODO: Documentation
# TODO: Inverse


class LinearPlusOneGate(ops.Gate, ops.TextDiagrammable, ops.ReversibleEffect, ops.CompositeGate):
	def __init__(self):
		pass

	def inverse(self):
		# TODO: write the decrement
		pass

	def text_diagram_info(self, args):
		syms = []
		for i in range(args.known_qubit_count):
			syms.append('[+1 : ' + str(i) + ']')
		syms = tuple(syms)
		return ops.TextDiagramInfo(syms, connected=True)
 
	def default_decompose(self, qubits):
		yield CnXLinearOp(*qubits)
		yield IncrementLinearWithBorrowedBitOp(*qubits)
"""
# Testing LinearPlusOneGate
for i in range(4, 11):
	for j in range(2**i):
		input_bs = format(j, '0' + str(i) + 'b')[::-1]
		output_bs = []

		carry = True
		for k in range(len(input_bs)):
			b = int(input_bs[k])
			if carry:
				if b:
					output_bs.append(0)
					carry = True
				else:
					carry = False
					output_bs.append(1)
			else:
				if b:
					output_bs.append(1)
					carry = False
				else:
					carry = False
					output_bs.append(0)

		output_bs = ''.join(str(b) for b in output_bs)

		output_bs = output_bs[:len(input_bs)]

		input_index = sum([2**(len(input_bs)-1 - j)*int(input_bs[j]) for j in range(len(input_bs))])
		output_index = sum([2**(len(input_bs)-1 - j)*int(output_bs[j]) for j in range(len(output_bs))])

		g = LinearPlusOneGate()
		op = g(*cirq.LineQubit.range(i))
		c = cirq.Circuit.from_ops(op)

		state_vector = [0] * (2 ** i)
		state_vector[input_index] = 1

		sv_prime = c.apply_unitary_effect_to_state(np.array(state_vector))
		new_index = np.argmax(sv_prime)
		if output_index != new_index:
			print(input_bs, output_bs, format(new_index, '0' + str(i) + 'b'))
		#print(input_index, output_index, new_index)
			
	print(c)
"""

		
