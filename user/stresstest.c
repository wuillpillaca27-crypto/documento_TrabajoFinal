#include "kernel/types.h"
#include "kernel/stat.h"
#include "user/user.h"
int main(int argc, char *argv[])
{
  int hijos = 0;
  printf("Iniciando prueba de carga...\n");
  for(int i = 0; i < 10; i++){
    int pid = fork();
    if(pid < 0) break;
    if(pid == 0){
      pause(500);
      exit(0);
    }
    hijos++;
  }
  for(int i = 0; i < hijos; i++) wait(0);
  printf("Prueba de carga finalizada\n");
  exit(0);
}
