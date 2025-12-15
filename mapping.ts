// src/mapping.ts
import { BigInt, Bytes } from "@graphprotocol/graph-ts"
import {
  DonationReceived,
  MilestonePaid,
  WaqfProject as WaqfProjectContract
} from "../generated/WaqfProject/WaqfProject"
import { Project, Donor, Contribution, Milestone } from "../generated/schema"

// Обработчик события DonationReceived
export function handleDonationReceived(event: DonationReceived): void {
  let projectAddress = event.address.toHexString()
  let project = Project.load(projectAddress)

  // Если проект еще не создан, создаем его
  if (project == null) {
    project = new Project(projectAddress)
    let contract = WaqfProjectContract.bind(event.address)
    project.beneficiary = contract.beneficiary()
    project.goalAmount = contract.goalAmount()
    project.deadline = contract.deadline()
    project.raisedAmount = BigInt.fromI32(0)
    project.state = "Fundraising"
    // ... и другие поля
  }

  // Обновляем общую собранную сумму проекта
  project.raisedAmount = project.raisedAmount.plus(event.params.amount)
  project.save()

  // --- Работа с донором ---
  let donorId = event.params.donor.toHexString()
  let donor = Donor.load(donorId)
  if (donor == null) {
    donor = new Donor(donorId)
    donor.totalDonated = BigInt.fromI32(0)
    donor.contributionsCount = 0
    donor.project = []
  }
  donor.totalDonated = donor.totalDonated.plus(event.params.amount)
  donor.contributionsCount = donor.contributionsCount + 1
  
  // Добавляем проект к донору, если его там еще нет
  let projects = donor.project
  if (!projects.includes(project.id)) {
      projects.push(project.id)
      donor.project = projects
  }
  donor.save()

  // --- Создаем запись о пожертвовании ---
  let contributionId = event.transaction.hash.toHexString()
  let contribution = new Contribution(contributionId)
  contribution.project = projectAddress
  contribution.donor = donorId
  contribution.amount = event.params.amount
  contribution.timestamp = event.block.timestamp
  contribution.save()
}

// Обработчик события MilestonePaid
export function handleMilestonePaid(event: MilestonePaid): void {
  let projectAddress = event.address.toHexString()
  let milestoneIndex = event.params.milestoneIndex
  let milestoneId = projectAddress + "-" + milestoneIndex.toString()

  let milestone = Milestone.load(milestoneId)
  if (milestone != null) {
    milestone.isPaid = true
    milestone.save()
  }
}
