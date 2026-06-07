#!/usr/bin/env python

from hardware import *
import log
import heapq
import math
##from gantt import *



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


class Loader():

    def __init__(self,fileSystem, memoryManager):
        ## asignación continua ---> self._lastMemoryDir = 0 
        self._fileSystem = fileSystem
        self._memoryManager = memoryManager
        self._pageSize = memoryManager.pageSize

    ##@property
    ##def lastMemoryDir(self):
      ##    return self._lastMemoryDir
    
   ## @lastMemoryDir.setter
    ##def lastMemoryDir_set(self,address):
      ##  self._lastMemoryDir = address

    def loadProgram(self, path):
        # carga el programa en la memoria desde el fileSystem y retorna la tabla de páginas creada para el proceso.
        #Falla si no es encontrado el archivo o no hay memoria suficiente.
        program = self._fileSystem.read(path)

        if program is None:
            log.logger.error(f"LOADER: Error, programa no encontrado en '{path}'")

        else:
            progSize = len(program.instructions)
            ## Usamos math.ceil() para redondear hacia arriba
            # ej: 9 instrucciones / 4 (pageSize) = 2.25 -> 3 páginas - (fragmentación interna)
            numPagesNeeded = math.ceil(progSize / self._pageSize) 
            allocatedFrames = self._memoryManager.allocateFrames(numPagesNeeded) ##lista
            
            if allocatedFrames is None:
                ##no hay memoria suficiente
                log.logger.error(f"LOADER: No se pudo cargar '{path}', memoria insuficiente.")
            else:
                # PageTable: Mapea {pagina_logica: frame_fisico}
                pageTable = {} ## es diccionario 
                for pageIndex, frameIndex in enumerate(allocatedFrames): ## enumerate provee las claves que toman los pageIndex:  
                    pageTable[pageIndex] = frameIndex ##ej:allocatedFrames: [7,3,1] (frames asignados para el programa dado): Page table queda: {0:7,1:3,2:1}
                
                log.logger.info(f"LOADER: Mapeo para '{path}': {pageTable}")
                
                ##Escribe el programa en los frames físicos 
                for logicalAddress, instruction in enumerate(program.instructions):## Itera por cada instrucción del programa 
                    ## Calculo de en qué página y offset va esta instrucción
                    pageNumber = logicalAddress // self._pageSize
                    offset = logicalAddress % self._pageSize

                    ##traducción: busca el frame fisico en la pt
                    frameNumber = pageTable[pageNumber]
                    ##dir física final
                    physicalAddress = (frameNumber * self._pageSize) + offset

                    # Escribir la instrucción en la memoria física
                    HARDWARE.memory.write(physicalAddress, instruction)

                log.logger.info(f"LOADER: Path '{path}' cargado en frames {allocatedFrames}")
                ##Devuelve la Page Table para que el Kernel se la dé al PCB
                return pageTable 
            
class Dispatcher():

    ##poner un proceso running
    def load(self,pcb):
        HARDWARE.mmu.resetTLB()

        pageTable = pcb.pageTable 
        for page, frame in pageTable.items():
            HARDWARE.mmu.setPageFrame(page, frame)

        HARDWARE.cpu.pc = pcb.pc    
        HARDWARE.timer.reset() 
        log.logger.info("\n Ejecutando programa: {name}".format(name=pcb.path)) 
        

    ##sacar un proceso running    
    def save(self,pcb):
        pcb.pc = HARDWARE.cpu.pc
        pcb.tempPriority = pcb.originalPriority ## cada vez que un proceso sale de cpu, se le reinicia la prioridad por si fue envejecido previamente.    
        HARDWARE.cpu.pc = -1      

class PCB():

    def __init__(self, pid, path, priority):   
        self._pageTable = None ## Inicia vacío
        self._pid = pid
        ##self._programBaseDir = programBaseDir
        self._pc = 0
        self._path = path
        self._state = NEW 
        self._originalPriority = priority  ##aging 
        self._tempPriority = priority   ##aging         
    
    @property
    def pid(self):
        return self._pid
    
    @property
    def pageTable(self):
        return self._pageTable
    def setPageTable(self, page_table):
        self._pageTable = page_table


   ## @property
    ##def programBaseDir(self):
      ##  return self._programBaseDir
    
    @property
    def pc(self):
        return self._pc
    
    @pc.setter
    def pc(self, newPc):
        self._pc = newPc

    @property
    def path(self):
        return self._path
    
    @property
    def state(self):
        return self._state
    
    
    def setState(self,newState):
        self._state = newState

    @property
    def tempPriority(self):
        return self._tempPriority
    
    #nuevo:
    
    @tempPriority.setter
    def tempPriority(self, newPriority):
        self._tempPriority = newPriority
    
    @property
    def originalPriority(self):
        return self._originalPriority
    
    def __lt__(self, otro):
        return self.pid < otro.pid
    
    def __repr__(self):
        return "PCB pid {pid}".format(pid=self.pid)

    """ @property
    def currentInstruction(self):
        return self.program.instruction(self.pc) """

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
        if self._runningPCB:
            self._runningPCB.setState(RUNNING)


    @property
    def getNewPID(self):
        return self._newPID


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
        pcb.setState(WAITING)
        self.kernel.ioDeviceController.runOperation(pcb, operation)

        if self.kernel.scheduler.readyQueue:
            pcbToLoad = self.kernel.scheduler.getNext()
            self.kernel.pcbTable.runningPCB = pcbToLoad
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1             ## dejamos el CPU IDLE


class IoOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):

        pcb = self.kernel.ioDeviceController.getFinishedPCB()

        log.logger.info(f"HANDLER (IO_OUT): Proceso {pcb.pid} terminó I/O.")
        self.kernel.handleArrivalRQ(pcb)

class KillInterruptionHandler(AbstractInterruptionHandler):
    
    def execute(self, irq):
        print("HANDLER (KILL): Recibida la IRQ de Kill")
        pcb = self.kernel.pcbTable.runningPCB
        self.kernel.dispatcher.save(pcb)
        pcb.setState(TERMINATED) 
        pageTable = pcb.pageTable
        pcbFrames = list(pageTable.values()) ##aextrae los frames del diccionario (pagetable) como una lista.
        self.kernel.memoryManager.releaseFrames(pcbFrames)
       
        readyQ = self.kernel.scheduler.readyQueue
        temp = len(readyQ) == 0

        if not temp:
           pcbToLoad = self.kernel.scheduler.getNext() 
           self.kernel.pcbTable.runningPCB = pcbToLoad
           pcbToLoad.setState(RUNNING)
           self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1  ## dejamos el CPU IDLE

        if temp and HARDWARE.ioDevice.is_idle:
            log.logger.info(" Program Terminado ")
            ##self.gantt.print_chart(self)
            HARDWARE.switchOff()
            
        
class NewInterruptionHandler(AbstractInterruptionHandler): 

    def execute(self, irq):
        parameters = irq.parameters
        path = parameters['path']
        priority = parameters['priority']
        
        log.logger.info(f"HANDLER (NEW): Recibida solicitud para cargar '{path}' con prioridad {priority}.")
        
        pageTable = self.kernel.loader.loadProgram(path)

        if pageTable is None:
            # Si pageTable es None, el Loader falló (sin memoria o archivo no encontrado)
            log.logger.error(f"HANDLER (NEW): Falló la carga de {path}. Proceso no creado.")
        else: 
            pid = self.kernel.pcbTable.getNewPID
            newPCB = PCB(pid, path, priority)
            newPCB.setPageTable(pageTable)
            self.kernel.pcbTable.addPCB(newPCB)

            log.logger.info(f"HANDLER (NEW): Proceso {newPCB.pid} creado.")
            self.kernel.handleArrivalRQ(newPCB)

          
class TimeoutInterruptionHandler(AbstractInterruptionHandler):  ##acá se realiza RR 

    def execute(self, irq):
        

        if self.kernel.scheduler.quantum == 0:
            return
        print("Terminó el quantum")
        pcbInCPU = self.kernel.pcbTable.runningPCB
        pcbToLoad = None
        
        
        if pcbInCPU is not None:
            
            self.kernel.dispatcher.save(pcbInCPU) 
            self.kernel.scheduler.addPCB(pcbInCPU) 
            pcbInCPU.setState(READY) 
            
            log.logger.info("Scheduler: Proceso {pid} expropiado por Round Robin.".format(pid=pcbInCPU.pid))
            
        if not self.kernel.scheduler.is_empty():
            pcbToLoad = self.kernel.scheduler.getNext() 
            self.kernel.pcbTable.runningPCB = pcbToLoad 
            self.kernel.dispatcher.load(pcbToLoad)
        else:
            self.kernel.pcbTable.runningPCB = None
            HARDWARE.cpu.pc = -1

class StatInterruptionHandler(AbstractInterruptionHandler): 
        def __init__(self, kernel):
            super().__init__(kernel)
            self.history = []  # guarda (tick, proceso)

        def execute(self, irq):
            tick = HARDWARE.clock.currentTick
            running = self.kernel.pcbTable.runningPCB
            
            if running:
                pid = running.pid
            else:
                pid = "IDLE"

            self.history.append((tick, pid))
            self.kernel.scheduler.handleTick() ##en cada tick, avisa a scheduler que chequee si hay que envejecer.
            print(f"[Tick {tick}] Ejecutando: {pid}")


class AbstractScheduler():

    def __init__(self):
        self._readyQueue = [] ##[(pcb,1),(pcb2,2),(pcb3,2)]

    @property
    def quantum(self):
        return 0

    def handleTick(self):
        pass
  
    def addPCB(self, pcb):
        log.logger.error("-- ADDPCB MUST BE OVERRIDDEN in class {classname}".format(classname=self.__class__.__name__))
        
    def getNext(self):
        log.logger.error("-- GETNEXT MUST BE OVERRIDDEN in class {classname}".format(classname=self.__class__.__name__))
        
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        log.logger.error("-- MUSTEXPROPIATE MUST BE OVERRIDDEN in class {classname}".format(classname=self.__class__.__name__))

    @property
    def readyQueue(self):
        return self._readyQueue
    
    def is_empty(self):
        return not self._readyQueue
    

class FCFSScheduler(AbstractScheduler):

    def addPCB(self, pcb):   
        self._readyQueue.append(pcb) 
        pcb.setState(READY)
        
    def getNext(self):
        print(self._readyQueue)
        return self._readyQueue.pop(0)
    
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return False

class RoundRobinScheduler(FCFSScheduler):  

    def __init__(self,quantum):
        super().__init__()
        print("quantum")
        self._quantum = quantum
        HARDWARE.timer.quantum = quantum  #se lo paso como paramentro directamente 
    
    @property
    def quantum(self):
        return self._quantum

class PrioritySchedulerBase(AbstractScheduler):
    
    MIN_PRIORITY = 1     # 1 es la prioridad más alta 

    def __init__(self):
        super().__init__()
        self._aging_counter = 0

    def addPCB(self, pcb):
        heapq.heappush(self._readyQueue, (pcb.tempPriority, pcb)) 
        pcb.setState(READY)
        
    def getNext(self): 
        _, nextPCB = heapq.heappop(self._readyQueue)
        return nextPCB
    
    def age(self):

        if not self._readyQueue:
            return 
            
        temporary_list = []
        
        # Extraer temporalmente todos los elementos del heap
        while self._readyQueue:
            _, pcb = heapq.heappop(self._readyQueue) 
            
            new_priority = max(self.MIN_PRIORITY, pcb.tempPriority - 1) 
            
            if new_priority != pcb.tempPriority:
                pcb.tempPriority = new_priority
                log.logger.info(f"AGING: Proceso {pcb.pid} mejoró prioridad a {pcb.tempPriority}")

            heapq.heappush(temporary_list, (pcb.tempPriority, pcb))

        self._readyQueue = temporary_list        
    
class NoPreemptivePriorityScheduler(PrioritySchedulerBase):
    print("USANDO PRIORIDAD NO EXPROPIATIVA CON AGING (EVENTO)")
                  
    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return False

class PreemptivePriorityScheduler(PrioritySchedulerBase):
    print("USANDO PRIORIDAD EXPROPIATIVA CON AGING")

    AGING_THRESHOLD = 3 ##tiempo (tick) max de proceso en readyQueue antes de aplicarle aging.
   
    def handleTick(self):
        ## Este método es llamado por el StatInterruptionHandler en CADA tick. Itera sobre todos los procesos en la readyQueue y aplica aging si es necesario.
        self._aging_counter += 1

        if self._aging_counter >= self.AGING_THRESHOLD:
            log.logger.info(f"--- AGING Check en Tick {HARDWARE.clock.currentTick} ---")
            self.age()
            self._aging_counter = 0  # Reiniciar el contador    

    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return pcbToAdd.tempPriority < pcbInCPU.tempPriority
    
class MemoryManager():
    
    def __init__(self,memorySize,pageSize):
        
        self._pageSize = pageSize
        self._totalFrames = memorySize // pageSize ##división entera //  

       ## La lista de frames libres es una pila con los índices de cada uno. 
       ## Por default todos estan libres.
        self._freeFrames = list(range(self._totalFrames)) ## rango de 0 al total de frames - 1 

        log.logger.info(f"MemoryManager inicializado. RAM: {memorySize}B, "
                        f"PageSize: {pageSize}B, Frames Totales: {self._totalFrames}")

    @property
    def freeFramesCount(self):
        ##Devuelve cuántos frames libres quedan.
        return len(self._freeFrames)
    @property
    def pageSize(self):
        ##Devuelve el tamaño de página configurado.
        return self._pageSize
    
    def allocateFrames(self, numPagesNeeded):
        ##asigna un número de frames para un nuevo proceso.
        if numPagesNeeded > self.freeFramesCount:
            # Error de memoria insuficiente
            log.logger.warning(f"MM: OUT OF MEMORY: Se pidieron {numPagesNeeded} frames, "
                             f"pero solo hay {self.freeFramesCount} libres.")
        else: # Sí hay memoria, se asigna.
            allocatedFrames = [] ##lista de frames asignados
            for _ in range(numPagesNeeded): 
                frameIndex = self._freeFrames.pop() ## saca el ultimo frame libre de la pila.
                allocatedFrames.append(frameIndex)
                
            log.logger.info(f"MM: Asignados {numPagesNeeded} frames. Índices: {allocatedFrames}")
            return allocatedFrames
        
    def releaseFrames(self, framesToRealese):
        ##Recibe una lista de índices de frames y los devuelve a la lista de frames libres
        self._freeFrames.extend(framesToRealese) ## extend agrega uno x uno los elementos en framesToRealese a la lista freeFrames.  
        log.logger.info(f"MM: Liberados {len(framesToRealese)} frames. (Total libres ahora: {self.freeFramesCount})")

class FileSystem():
    def __init__(self):
        self._drive = {} ## diccionario clave(path), valor (program) path = str
        log.logger.info("FILE SYSTEM (Hard Drive) inicializado.")
    
    def write(self, path, program):
        ##si la ruta ya existe, la sobrescribe
        log.logger.info(f"FILE SYSTEM: Escribiendo programa en la ruta '{path}'")
        self._drive[path] = program

    def read(self, path):
        ##si la ruta esta en el disco, lo devuelve a partir de su path, si no, imprime un error.
        if path in self._drive:
            log.logger.info(f"FILE SYSTEM: Leyendo programa desde la ruta '{path}'")
            return self._drive[path]
            
        else:
            log.logger.error(f"FILE SYSTEM: Error 'Archivo No Encontrado' en la ruta '{path}'")
            

# emulates the core of an Operative System
class Kernel():

    def __init__(self,memorySize, pageSize):
        ## setup interruption handlers
        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

        ioInHandler = IoInInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_IN_INTERRUPTION_TYPE, ioInHandler)

        ioOutHandler = IoOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_OUT_INTERRUPTION_TYPE, ioOutHandler)

        newHandler = NewInterruptionHandler(self)
        HARDWARE.interruptVector.register(NEW_INTERRUPTION_TYPE, newHandler)

        timeoutHandler = TimeoutInterruptionHandler(self)
        HARDWARE.interruptVector.register(TIMEOUT_INTERRUPTION_TYPE, timeoutHandler)
        
        statHandler = StatInterruptionHandler(self)
        HARDWARE.interruptVector.register(STAT_INTERRUPTION_TYPE, statHandler)
       
       ##Las estadisticas se habilitan seteando el flag enable_stats del CPU
        HARDWARE.cpu.enable_stats = True 

        
        ## controls the Hardware's I/O Device
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice) 

        self._dispatcher = Dispatcher()
        self._pcbTable = PCBTable()
        self._scheduler = FCFSScheduler()
        
        ##nuevo
        self._memoryManager = MemoryManager(memorySize,pageSize)  ##Tamaño de la memoria, Tamaño de página. 
        self._fileSystem = FileSystem() 

           ##nuevas dependencias del loader
        self._loader = Loader(self._fileSystem,self._memoryManager)

    ##maneja la llegada de procesos que salen DE IO o que son recien creados, a la readyQueue.
    def handleArrivalRQ(self, arrivedPCB):
        
        pcbInCPU = self.pcbTable.runningPCB
        log.logger.info(f"KERNEL: Proceso {arrivedPCB.pid} llega a ReadyQueue.")
        self.scheduler.addPCB(arrivedPCB)
   
        if pcbInCPU is None: ##No hay nada en CPU
            log.logger.info("KERNEL: CPU libre. Despachando siguiente proceso.")
            self.loadNextProcess()

        elif self.scheduler.mustExpropiate(pcbInCPU, arrivedPCB): ##Hay que expropiar
                log.logger.info(f"KERNEL: Expropiando a {pcbInCPU.pid} por {arrivedPCB.pid}")
                self.preemptRunningProcess()
    
    def loadNextProcess(self):
    
        nextPCB = self.scheduler.getNext()
        self.pcbTable.runningPCB = nextPCB
        self.dispatcher.load(nextPCB)
        nextPCB.setState(RUNNING)

    def preemptRunningProcess(self):
        ## Hace la expropiación 
        pcbOut = self.pcbTable.runningPCB

        self.dispatcher.save(pcbOut)
        log.logger.info(f"DISPATCHER: Proceso {pcbOut.pid} vuelve a ReadyQueue.")
        self.scheduler.addPCB(pcbOut)
        self.loadNextProcess()

    
    
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
    def scheduler(self):
        return self._scheduler
    
    @property
    def memoryManager(self):
        return self._memoryManager
    
    @property
    def fileSystem(self):
        return self._fileSystem
    
    ## emulates a "system call" for programs execution
    def run(self, program, path, priority):
        self._fileSystem.write(path, program)
        log.logger.info(f"KERNEL: Programa '{path}' instalado en FileSystem.")
        
        parameters = {'priority': priority, 'path' : path}
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, parameters)

        HARDWARE.interruptVector.handle(newIRQ)
        log.logger.info(f"KERNEL: Solicitud de ejecución enviada para '{path}'.")

    def __repr__(self):
        return "Kernel "

