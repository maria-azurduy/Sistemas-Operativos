#!/usr/bin/env python

from hardware import *
import log



## emulates a compiled program
class Program():

    def __init__(self, name, instructions):
        self._name = name
        self._instructions = self.expand(instructions)

    @property
    def name(self):
        return self._name

    @property
    def instructions(self):
        return self._instructions

    def addInstr(self, instruction):
        self._instructions.append(instruction)

    def expand(self, instructions):
        expanded = []
        for i in instructions:
            if isinstance(i, list):
                ## is a list of instructions
                expanded.extend(i)
            else:
                ## a single instr (a String)
                expanded.append(i)
            
        ## now test if last instruction is EXIT
        ## if not... add an EXIT as final instruction
        last = expanded[-1]
        if not ASM.isEXIT(last):
            expanded.append(INSTRUCTION_EXIT)

        return expanded

    def __repr__(self):
        return "Program({name}, {instructions})".format(name=self._name, instructions=self._instructions)


## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))



class KillInterruptionHandler(AbstractInterruptionHandler):
    def execute(self, irq):      ## 5. KillInterruptionHandler decide si sigue ejecutando o apaga el equipo.  
        if self.kernel.has_more_programs():
            log.logger.info(" Program finished, loading next one...")
            self.kernel.run_next_program()
        else:
            log.logger.info(" All programs finished. Shutting down.")
            HARDWARE.switchOff()    ##ahora que hay una lista de programas, lo debe manejar con alternativa condicional.

    ##def execute(self, irq):          esto es en caso de tener un solo programa
    ##    log.logger.info(" Program Finished ")
    ##    # por ahora apagamos el hardware porque estamos ejecutando un solo programa
    ##    HARDWARE.switchOff()


# emulates the core of an Operative System
class Kernel():

    def __init__(self):
        ## setup interruption handlers
        self._batch = []         ##inicializa el batch
        killHandler = KillInterruptionHandler(self) ## 4. InterruptVector llama al handler registrado (la clase killinterruption)        
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

    def load_batch(self, programs):
        self._batch = programs   ## le carga los programas al batch, definidos en main
    
    def has_more_programs(self):           ##chequea si la lista interna _batch está vacía o no.
        return len(self._batch) > 0
    
    def run_next_program(self):               ##2 Kernel ejecuta el primer programa
        if self.has_more_programs():           ##saca el próximo de la cola y lo ejecuta.
            current = self._batch.pop(0)   
            self.run(current)

    def load_program(self, program):
        # loads the program in main memory  
        progSize = len(program.instructions)
        for index in range(0, progSize):
            inst = program.instructions[index]
            HARDWARE.memory.write(index, inst)

    ## emulates a "system call" for programs execution  
    def run(self, program):
        self.load_program(program)
        log.logger.info("\n Executing program: {name}".format(name=program.name))
        log.logger.info(HARDWARE)

        # set CPU program counter at program's first intruction
        HARDWARE.cpu.pc = 0


    def __repr__(self):
        return "Kernel "


