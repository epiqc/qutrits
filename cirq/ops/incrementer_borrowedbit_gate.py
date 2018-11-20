from cirq.ops import gate_features
from cirq import ops
import cirq

# Requires use of cnx_borrowed_bit_gate.py
from cirq.ops import cnx_borrowed_bit_gate

# Source: https://algassert.com/circuits/2015/06/12/Constructing-Large-Increment-Gates.html
# Implemented by: Jonathan M. Baker (jmbaker@uchicago.edu)
# Verfified on all pure state inputs up to 10 qubits.

# TODO: Documentation

class IncrementLinearWithBorrowedBitGate(ops.Gate, ops.TextDiagrammable, ops.ReversibleEffect, ops.CompositeGate):
	def __init__(self):
		pass

	def inverse(self):
		pass

	def text_diagram_info(self, args):
		# puts a [+1 : index] in inputs ordered by their bit order. I.e. low bit = 0
		syms = []
		for i in range(args.known_qubit_count - 1):
			syms.append('[+1 : ' + str(i) + ']')
		syms = tuple(syms)
		return ops.TextDiagramInfo(syms+('BB',), connected=True)

	def default_decompose(self, qubits):
		# Expected qubits = (input, borrowed_bit)
		# Requires use of CnXLinearBorroedBit

		# http://algassert.com/circuits/2015/06/12/Constructing-Large-Increment-Gates.html
		# First Split Incrementer from Borrowed Bit
		# Repeat until each +1 / -1 has access to n borrowed bits

		# Note 
		#	@			 -------   X 
		#	|			|		|
		# -------		|		|
		#|		 |		|		|
		#|		 |   =	|	+1	|
		#|  +1	 |		|		|	
		#|		 |		|		|
		#|_______|		|_______|



		return self._split_incrementer_borrowed_bit(list(qubits), list(qubits))

	def _split_incrementer_borrowed_bit(self, current, qubits):
		"""
			Args:
				current: list of qubits currently being broken down; if len(current) < len(qubits)/2 move to n-borrowed-bit else recurse
				qubits: a list keeping track of each of the qubits for reference
		"""
		# We err on the side of the bottom being shorter than the top -> will require calling this function 2 fewer times

		top_half = current[:(len(current)-1)//2 + 1]
		bottom_half = current[(len(current)-1)//2 + 1:]

		# len(bottom) <= len(qubits)/2 
		correctly_arranged_qubits_with_borrowed_bits = self._prepare_bb_bits([bottom_half[-1]] + bottom_half[:-1], qubits)
		yield self._linear_increment_n_bb(correctly_arranged_qubits_with_borrowed_bits)
		yield ops.X(bottom_half[-1])
		
		# CX Block
		for i in range(len(bottom_half) - 1):
			yield ops.CNOT(bottom_half[-1], bottom_half[i])

		# Perform a CnX Gate
		cnx_q_list = top_half + [bottom_half[-1]] + [bottom_half[0]]
		yield CnxLinearBorrowedBit(*cnx_q_list)

		# CX Block
		for i in range(len(bottom_half) - 1):
			yield ops.CNOT(bottom_half[-1], bottom_half[i])

		# len(bottom) <= len(top)
		for i in range(len(bottom_half)-1):
			yield ops.X(bottom_half[i])
		yield self._linear_increment_n_bb(correctly_arranged_qubits_with_borrowed_bits)
		for i in range(len(bottom_half)):
			yield ops.X(bottom_half[i])

		# CX Block
		for i in range(len(bottom_half) - 1):
			yield ops.CNOT(bottom_half[-1], bottom_half[i])

		# Perform a CnX Gate
		# TODO: Remove the decompose part
		yield CnxLinearBorrowedBit(*cnx_q_list)

		# CX Block
		for i in range(len(bottom_half) - 1):
			yield ops.CNOT(bottom_half[-1], bottom_half[i])
		
		if 2 * len(top_half) <= len(qubits):
			correctly_arranged_qubits_with_borrowed_bits = self._prepare_bb_bits(top_half, qubits)
			yield self._linear_increment_n_bb(correctly_arranged_qubits_with_borrowed_bits)
		else:
			# Divide one more time
			# print(top_half + self._find_borrowable(top_half, current))
			yield self._split_incrementer_borrowed_bit(top_half + self._find_borrowable(top_half, current), qubits)
		
	def _linear_increment_n_bb(self, qubits):
		# Expecting qubits = [x1, A, x2, B, x3, C, ..., Z] i.e. alternating bb with ob = output bit
		for i in range(1, len(qubits) - 2, 2):
			yield ops.CNOT(qubits[0], qubits[i])
			yield ops.X(qubits[i+1])
		yield ops.X(qubits[-1])

		for i in range(2, len(qubits) - 1, 2):
			yield ops.CNOT(qubits[i-2], qubits[i-1])
			yield ops.CCX(qubits[i], qubits[i-1], qubits[i-2])
			yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
		yield ops.CNOT(qubits[-2], qubits[-1])

		for i in reversed(range(2, len(qubits) - 1, 2)):
			yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
			yield ops.CCX(qubits[i], qubits[i-1], qubits[i-2])
			yield ops.CNOT(qubits[i], qubits[i-1])

		for i in range(2, len(qubits) - 1, 2):
			yield ops.X(qubits[i])

		for i in range(2, len(qubits) - 1, 2):
			yield ops.CNOT(qubits[i-2], qubits[i-1])
			yield ops.CCX(qubits[i], qubits[i-1], qubits[i-2])
			yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
		yield ops.CNOT(qubits[-2], qubits[-1])

		for i in reversed(range(2, len(qubits) - 1, 2)):
			yield ops.CCX(qubits[i-2], qubits[i-1], qubits[i])
			yield ops.CCX(qubits[i], qubits[i-1], qubits[i-2])
			yield ops.CNOT(qubits[i], qubits[i-1])

		for i in range(1, len(qubits) - 2, 2):
			yield ops.CNOT(qubits[0], qubits[i])
	
	def _prepare_bb_bits(self, current, qubits):
		new_list = []
		for q in current:
			new_list.append(self._find_borrowable(current + new_list, qubits)[0])
			new_list.append(q)
		return new_list

	def _find_borrowable(self, current, qubits):
		for q in qubits:
			if q not in current:
				return [q]

IncrementLinearWithBorrowedBitOp = IncrementLinearWithBorrowedBitGate()

"""
# VERIFICIATION FOR INCREMENT W/ BB
for i in range(4, 9):
	for j in range(2**i):
		input_bs = format(j, '0' + str(i) + 'b')[::-1]
		output_bs = []

		carry = True
		for k in range(len(input_bs) - 1):
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

		output_bs.append(input_bs[-1])
		output_bs = ''.join(str(b) for b in output_bs)

		output_bs = output_bs[:len(input_bs)]

		input_index = sum([2**(len(input_bs)-1 - j)*int(input_bs[j]) for j in range(len(input_bs))])
		output_index = sum([2**(len(input_bs)-1 - j)*int(output_bs[j]) for j in range(len(output_bs))])

		g = IncrementLinearWithBorrowedBitGate()
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