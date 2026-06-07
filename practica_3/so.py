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


## emulates an Input/Output device controller (driver)
class IoDeviceController():

    def __init__(self, device):
        self._device = device
        self._waiting_queue = []
        self._currentPCB = None

    #nueva property para la cola de espera --
    @property
    def waiting_queue(self):
        return self._waiting_queue

    def runOperation(self, pcb, instruction):
        pair = {'pcb': pcb, 'instruction': instruction}
        # append: adds the element at the end of the queue
        self._waiting_queue.append(pair)
        # try to send the instruction to hardware's device (if is idle)
        self.__load_from_waiting_queue_if_apply()

    def getFinishedPCB(self):
        finishedPCB = self._currentPCB
        self._currentPCB = None
        self.__load_from_waiting_queue_if_apply()
        return finishedPCB

    def __load_from_waiting_queue_if_apply(self):
        if (len(self._waiting_queue) > 0) and self._device.is_idle:
            ## pop(): extracts (deletes and return) the first element in queue
            pair = self._waiting_queue.pop(0)
            #print(pair)
            pcb = pair['pcb']
            instruction = pair['instruction']
            self._currentPCB = pcb
            self._device.execute(instruction)


    def __repr__(self):
        return "IoDeviceController for {deviceID} running: {currentPCB} waiting: {waiting_queue}".format(deviceID=self._device.deviceId, currentPCB=self._currentPCB, waiting_queue=self._waiting_queue)

## 5 estados --
NEW = "new"
WAITING = "waiting"
READY = "ready"
RUNNING = "running"
TERMINATED = "terminated"

## 6.2: Implementar los componentes del S.O. --

class Loader():

    def __init__(self):
        self._lastMemoryDir = 0 

    @property
    def lastMemoryDir(self):
        return self._lastMemoryDir
    
    @lastMemoryDir.setter
    def lastMemoryDir_set(self,address):
        self._lastMemoryDir = address

    def load_program(self, program):
        # carga el programa en la memoria y retorna el direccion base donde se cargo.  

        baseDir = self._lastMemoryDir 
        progSize = len(program.instructions)

        for index in range(0, progSize):
            inst = program.instructions[index]
            HARDWARE.memory.write(index + baseDir, inst)
        self._lastMemoryDir += progSize 
         
        return baseDir 



class Dispatcher():

    ##poner un proceso running
    def load(self,pcb):
        HARDWARE.cpu.pc = pcb.pc    ## carga un proceso en CPU
        HARDWARE.mmu.baseDir = pcb.programBaseDir ##cargo baseDir de mi proceso running, ejecutandose en CPU
        log.logger.info("\n Executing program: {name}".format(name=pcb.path)) #{name}".format(name=pcb.path)

    ##sacar un proceso running    
    def save(self,pcb):
        pcb.pc = HARDWARE.cpu.pc    ## salva el estado de la CPU en el PCB y 
        HARDWARE.cpu.pc = -1        ##deja CPU en IDLE hasta el proximo load()

class PCB():

    def __init__(self, pid, programBaseDir, path):
        self._pid = pid
        self._programBaseDir = programBaseDir
        self._pc = 0
        self._path = path
        self._state = NEW ##revisar
    
    @property
    def pid(self):
        return self._pid
    
    @property
    def programBaseDir(self):
        return self._programBaseDir
    
    @property
    def pc(self):
        return self._pc
    
    @pc.setter
    def pc(self, newPc):
        self._pc = newPc

    @property
    def path(self):
        return self._path
    
    def state(self, newState):
        self._state = newState



class PCBTable():

    def __init__(self):
        self._PCBTable = []
        self._newPID = 1
        self._runningPCB = None
    
    
    def addPCB(self, PCB):
        self._PCBTable.append(PCB)
        self._newPID += 1

    def removePCB(self, PID):
        pass
  
    @property
    def runningPCB(self):
        return self._runningPCB
    
    @runningPCB.setter
    def runningPCB(self, newRunningPCB):
        self._runningPCB = newRunningPCB
    
    @property
    def getNewPID(self):
        return self._newPID


class ReadyQueue():
    
    def __init__(self):
        self._readyQueue = []

    @property
    def readyQueue(self):
        return self._readyQueue
    
    def addPCB(self, pcb):
        self._readyQueue.append(pcb)

    def isEmpty(self):
        return len(self._readyQueue) == 0


## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))


class IoInInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):

        operation = irq.parameters
        pcb = self.kernel.pcbTable.runningPCB 
        self.kernel.dispatcher.save(pcb)
        pcb.state(WAITING)
        self.kernel.ioDeviceController.runOperation(pcb, operation)

        if self.kernel.readyQueue.readyQueue:
            pcbToLoad = self.kernel.readyQueue.readyQueue.pop(0)
            self.kernel.pcbTable.runningPCB = pcbToLoad
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1             ## dejamos el CPU IDLE


class IoOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):

        pcb = self.kernel.ioDeviceController.getFinishedPCB()

        if self.kernel.pcbTable.runningPCB:
            pcb.state(READY) 
            self.kernel.readyQueue.addPCB(pcb)
        else:
            self.kernel.pcbTable.runningPCB = pcb
            pcb.state(RUNNING)
            self.kernel.dispatcher.load(pcb)


class KillInterruptionHandler(AbstractInterruptionHandler):
    
    def execute(self, irq):
        pcb = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(pcb)
        pcb.state(TERMINATED) 

        readyQ = self.kernel.readyQueue.readyQueue
        temp = readyQ.isEmpty()

        if not temp:
            pcbToLoad = readyQ.pop(0)
            self.kernel.pcbTable.runningPCB = pcbToLoad
            pcbToLoad.state(RUNNING)
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1  ## dejamos el CPU IDLE

        if temp and HARDWARE.ioDevice.is_idle:
            log.logger.info(" Program Finished ")
            HARDWARE.switchOff()
        


class NewInterruptionHandler(AbstractInterruptionHandler): 

    def execute(self, irq):
        program = irq.parameters
        pid = self.kernel.pcbTable.getNewPID
        programBaseDir = self.kernel.loader.load_program(program)
        newPCB = PCB(pid, programBaseDir, program.name)
        self.kernel.pcbTable.addPCB(newPCB)

        if self.kernel.pcbTable.runningPCB:
            newPCB.state(READY)
            self.kernel.readyQueue.addPCB(newPCB)
        else:
            self.kernel.dispatcher.load(newPCB)        #cargo el programa
            newPCB.state(RUNNING)                   # el estado pasa a ser RUNNING
            self.kernel.pcbTable.runningPCB = newPCB   
            

# emulates the core of an Operative System
class Kernel():

    def __init__(self):
        ## setup interruption handlers
        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

        ioInHandler = IoInInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_IN_INTERRUPTION_TYPE, ioInHandler)

        ioOutHandler = IoOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_OUT_INTERRUPTION_TYPE, ioOutHandler)

        newHandler = NewInterruptionHandler(self)
        HARDWARE.interruptVector.register(NEW_INTERRUPTION_TYPE, newHandler)

        ## controls the Hardware's I/O Device
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice)

        self._loader = Loader()
        self._dispatcher = Dispatcher()
        self._pcbTable = PCBTable()
        self._readyQueue = ReadyQueue()
    


    @property
    def ioDeviceController(self):
        return self._ioDeviceController
    
    @property
    def loader(self):
        return self._loader
    
    @property
    def dispatcher(self):
        return self._dispatcher
    
    @property
    def pcbTable(self):
        return self._pcbTable
    
    @property
    def readyQueue(self):
        return self._readyQueue
    

    ## emulates a "system call" for programs execution
    def run(self, program):
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, program)
        HARDWARE.interruptVector.handle(newIRQ)
        log.logger.info(HARDWARE)

    def __repr__(self):
        return "Kernel "

