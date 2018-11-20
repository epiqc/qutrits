from cirq import ops
from cirq import qutrit
from cirq.qutrit import raw_types
from cirq.qutrit import common_gates
import cirq

class BTBCnUGate(raw_types.TernaryLogicGate,
                ops.CompositeGate,
                ops.TextDiagrammable):
	def __init__(self, u_gate=common_gates.F01):
		self.u_gate = u_gate

	def validate_trits(self, trits):
		super().validate_trits(trits)
		assert len(trits) > 0, 'Gate only operates on one or more qutrits'

	def applied_to_trits(self, trits):
		control_triggered = (all(trit==1 for trit in trits[:-1]))
		if control_triggered:
			trits[-1] = self.u_gate.applied_to_trits(trits[-1])
		return trits

	def inverse(self):
		return BTBCnUGate(u_gate=self.u_gate.inverse())

	def text_diagram_info(self, args):
		base_info = self.u_gate.text_diagram_info(args)
		c_syms = ('@',) * (int(args.known_qubit_count) - 1)
		return ops.TextDiagramInfo(c_syms+base_info.wire_symbols, exponent=base_info.exponent, connected=True)

	def default_decompose(self, qutrits):

		yield self._decompose_first_layer(list(qutrits), uncompute=False)
		yield self._decompose_first_layer(list(qutrits), uncompute=True)

	def _decompose_first_layer(self, qutrits, uncompute=False):
		# Expecting just a long list of qubits [q1, q2, ..., q2, T]
		# Set the operation
		operation = common_gates.MinusOne if uncompute else common_gates.PlusOne
		qt = []

		target = qutrits[-1]
		controls = qutrits[:-1]

		for i in range(0, len(controls)-2, 4):
			yield qutrit.ControlledTernaryGate(operation, ((1,), (1,)))(controls[i], controls[i+2], controls[i+1])
			qt.append(controls[i+1])
			if i + 3 < len(controls):
				qt.append(controls[i+3])

		if len(controls) - i == 5:
			yield operation(controls[-1])
			qt.append(controls[-1])
		elif len(controls) - i == 6:
			yield qutrit.ControlledTernaryGate(operation, ((1,),))(controls[-2], controls[-1])
			qt.append(controls[-1])

		if not uncompute:
			last = []
			yield self._decompose_middle_layers(qt, last)
			if len(last) == 1:
				yield qutrit.ControlledTernaryGate(self.u_gate, ((2,),))(last[0], target)
			elif len(last) == 2:
				yield qutrit.ControlledTernaryGate(self.u_gate, ((2,), (1,)))(last[0], last[1], target)
			yield cirq.inverse(self._decompose_middle_layers(qt, last))

	def _decompose_middle_layers(self, qutrits, last):
		qt = []
		if len(qutrits) == 1:
			last.append(qutrits[0])
		elif len(qutrits) == 2:
			last.append(qutrits[0])
			last.append(qutrits[1])
		else:
			for i in range(0, len(qutrits) - 2, 4):
				yield qutrit.ControlledTernaryGate(common_gates.PlusOne, ((2,), (2,)))(qutrits[i], qutrits[i+2], qutrits[i+1])
				qt.append(qutrits[i+1])
				if i + 3 < len(qutrits):
					qt.append(qutrits[i+3])

			if len(qutrits) - i == 5:
				qt.append(qutrits[-1])
			elif len(qutrits) - i == 6:
				yield qutrit.ControlledTernaryGate(common_gates.PlusOne, ((2,),))(qutrits[-2], qutrits[-1])
				qt.append(qutrits[-1])

			if len(qt) > 0:
				yield self._decompose_middle_layers(qt, last)

