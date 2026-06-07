from hardware import *
from so import *
import log


##
##  MAIN 
##
if __name__ == '__main__':
    log.setupLogger()
    log.logger.info('Starting emulator')
    


    memorySize = 32
    pageSize = 4  

    HARDWARE.setup(memorySize)
    HARDWARE.mmu.frameSize = pageSize

    ## new create the Operative System Kernel
    # "booteamos" el sistema operativo
    kernel = Kernel(memorySize,pageSize)



    # Ahora vamos a intentar ejecutar 3 programas a la vez
    ##################
    prg1 = Program("prg1.exe", [ASM.CPU(5), ASM.IO(), ASM.CPU(4), ASM.IO(), ASM.CPU(5)])
    prg2 = Program("prg2.exe", [ASM.CPU(10)])
    prg3 = Program("prg3.exe", [ASM.CPU(6), ASM.IO(), ASM.CPU(1)])

    # execute all programs 
    kernel.run(prg1, "prg1.exe", 3)
    kernel.run(prg2, "prg2.exe", 5)
    kernel.run(prg3, "prg3.exe", 1)

    ## Switch on computer

    HARDWARE.switchOn()

## https://excalidraw.com/#room=ca478e577b22db29b113,p9q9S1xBQQVkjHuFSYYSRQ 
## GRÁFICO DE MEMORIA.  