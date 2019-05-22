This is the code accompanying Asymptotic Improvements to Quantum Circuits via Qutrits.

The code is built on top of the 0.4.0.dev35 version of cirq. It can be installed by running "python setup.py install". The results of our simulations are in the results/ directory. Our results can be reproduced by following the code block below, for each of the different noise models.

The quantum trajectories style simulation is accomplished in the `apply_unitary_effect_to_state(...)` method. In principle, the code can be generalized for arbitrary qudit levels by setting QUDIT_LEVELS in cirq/__init__.py. However, the specific gate set and noise models provided here are for qutrits.

.. code-block:: python

  import cirq
  from cirq import qutrit
  import numpy as np

  N = 14
  g = qutrit.BTBCnUGate()
  op = g(*cirq.LineQubit.range(N))
  c = cirq.Circuit.from_ops(op.default_decompose(), strategy=cirq.InsertStrategy.EARLIEST)

  # currently available noise models in cirq/circuits/circuit.py are:
  # CurrentSuperconductingQCErrors, FutureSuperconductingQCErrors, FutureSuperconductingQCErrorsBetterT1,
  # FutureSuperconductingQCErrorsBetterGates, FutureSuperconductingQCErrorsBetterT1AndGates,
  # DressedQutritErrors, BareQutritErrors
  noise_model = cirq.circuits.circuit.CurrentSuperconductingQCErrors()


  def get_random_state(n):
      rand_state2 = np.zeros(2 ** n, np.complex64)
      rand_state2.real = np.random.randn(2 ** n)
      rand_state2.imag = np.random.randn(2 ** n)
      rand_state2 /= np.linalg.norm(rand_state2)
      rand_state3 = np.zeros(3 ** n, np.complex64)
      for i, val in enumerate(rand_state2):
          rand_state3[int(bin(i)[2:], 3)] = val
      return rand_state3

  for _ in range(1000):
      print(c.apply_unitary_effect_to_state(get_random_state(N), noise_model=noise_model)[0])

-----------


.. image:: https://github.com/quantumlib/cirq/blob/master/docs/Cirq_logo_color.svg
  :alt: Cirq
  :width: 500px

Cirq is a Python library for writing, manipulating, and optimizing quantum
circuits and running them against quantum computers and simulators.

.. image:: https://travis-ci.com/quantumlib/Cirq.svg?token=7FwHBHqoxBzvgH51kThw&branch=master
  :target: https://travis-ci.com/quantumlib/Cirq
  :alt: Build Status

.. image:: https://badge.fury.io/py/cirq.svg
    :target: https://badge.fury.io/py/cirq

Installation
------------

Follow these
`instructions <https://cirq.readthedocs.io/en/latest/install.html>`__.

Hello Qubit
-----------

A simple example to get you up and running:

.. code-block:: python

  import cirq

  # Pick a qubit.
  qubit = cirq.GridQubit(0, 0)

  # Create a circuit
  circuit = cirq.Circuit.from_ops(
      cirq.X(qubit)**0.5,  # Square root of NOT.
      cirq.measure(qubit, key='m')  # Measurement.
  )
  print("Circuit:")
  print(circuit)

  # Simulate the circuit several times.
  simulator = cirq.google.XmonSimulator()
  result = simulator.run(circuit, repetitions=20)
  print("Results:")
  print(result)

Example output:

.. code-block:: bash

  Circuit:
  (0, 0): ───X^0.5───M('m')───
  Results:
  m=11000111111011001000


Documentation
-------------

See
`here <https://cirq.readthedocs.io/en/latest/>`__
or jump into the
`tutorial <https://cirq.readthedocs.io/en/latest/tutorial.html>`__.

Contributing
------------

We welcome contributions. Please follow these
`guidelines <https://github.com/quantumlib/cirq/blob/master/CONTRIBUTING.md>`__.

See Also
--------

For those interested in using quantum computers to solve problems in
chemistry and materials science, we encourage exploring
`OpenFermion <https://github.com/quantumlib/openfermion>`__ and
its sister library for compiling quantum simulation algorithms in Cirq,
`OpenFermion-Cirq <https://github.com/quantumlib/openfermion-cirq>`__.

Disclaimer
----------

Copyright 2018 The Cirq Developers. This is not an official Google product.
