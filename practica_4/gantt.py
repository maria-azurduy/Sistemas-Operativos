from tabulate import * 
import log
# Definición de los estados que usa el gráfico
STATE_RUNNING_CPU = "CPU"
STATE_RUNNING_IO = "IO"
STATE_READY = "."
STATE_EMPTY = " "

class GraficoGantt:
    def __init__(self, kernel):
        self.kernel = kernel
        self.history = {} # { "prg1_name": [" ", "CPU", ".", ...], "prg2_name": [".", ".", "CPU", ...] }
        self.tickCount = 0 ##ticks ejecutados hasta ahora.
    
    def trackList(self,kernel):  
        allPCBs = kernel.pcbTable.PCBTable
        runningPCB = kernel.pcbTable.runningPCB        
        currentPIDs = set()

        ##Registra el estado de todos los PCBs actuales
        for pcb in allPCBs: 
            pcbPID = pcb.pid
            currentPIDs(pcbPID)

        ## Si es un proceso nuevo, inicializa su historial con "vacío"
        if pcbPID not in self._history:
                self._history[pcbPID] = [STATE_EMPTY] * self.tickCount
    
        if pcb == runningPCB:
            instruction = pcb.currentInstruction()
            currentState = pcb.state()
            ## es IO
            if instruction == "IO":
                currentState(STATE_RUNNING_IO) 
            else: ## es CPU
                currentState(STATE_RUNNING_CPU)

        elif currentState() == "READY":    
                currentState(STATE_READY)
        else:
                currentState(STATE_EMPTY)
                
        self._history[pcbPID].append(currentState) 
        
        terminatedPIDs = set(self._history.keys()) - currentPIDs(pcbPID)
        for name in terminatedPIDs:
            self._history[pcbPID].append(STATE_EMPTY)
        
        self._tick_count += 1


    def print_gantt(self):
        if self._history:
            print("\n--- Diagrama de Gantt (Simulación) ---")
            # 1. Headers (Columnas): "Programa", 0, 1, 2, 3, ...
            headers = ["Programa"] + list(range(self._tick_count))
            # 2. Data (Filas)
            table_data = []
            for pcbPID, history in self._history.items():
                full_history = history + [STATE_EMPTY] * (self._tick_count - len(history))
                table_data.append([pcbPID] + full_history)
            # 3. Imprimir la tabla
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
