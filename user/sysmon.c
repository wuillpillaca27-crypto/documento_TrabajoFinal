#include "kernel/types.h"
#include "kernel/stat.h"
#include "kernel/metrics.h"
#include "user/user.h"
static struct sysmetrics m;
static char *states[] = {
   [0] = "UNUSED", [1] = "USED",
   [2] = "SLEEPING", [3] = "RUNNABLE",
   [4] = "RUNNING", [5] = "ZOMBIE"
};
int main(int argc, char *argv[])
{
   while(1){
     if(getmetrics(&m) == 0){
       printf("METRIC| %d| %d| %d| %d| %d| %d\n",
              m.ticks, (int)(m.free_mem / 1024),
              m.total_procs, m.running, m.runnable,
              m.sleeping);
       for(int i = 0; i < m.proc_count; i++){
         int st = m.procs[i].state;
         char *name = st >= 0 && st <= 5 ? states[st] : "UNKNOWN";
         printf("PROC| %d| %s| %d| %s\n", m.procs[i].pid,
                name, (int)(m.procs[i].sz / 1024),
                m.procs[i].name);
       }
       printf("END_FRAME\n");
     }
     pause(10);
   }
   exit(0);
}
